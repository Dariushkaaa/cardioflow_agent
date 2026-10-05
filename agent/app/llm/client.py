"""Клиент LLM: GigaChat (OAuth + Tool Calling через functions) и любой OpenAI-совместимый API.

GigaChat:
  1. Ключ авторизации (LLM_API_KEY, base64 от "client_id:client_secret") обменивается на access_token:
       POST https://ngw.devices.sberbank.ru:9443/api/v2/oauth
       Authorization: Basic <ключ>, RqUID: <uuid4>, тело scope=GIGACHAT_API_PERS
     Токен живет ~30 минут: кэшируется и обновляется заранее (а при ответе 401 - принудительно).
  2. Запросы идут в POST {LLM_BASE_URL}/chat/completions с Authorization: Bearer <access_token>.
  3. Вызов функций: в запрос передаются functions + function_call=auto, а ответ приходит как
     message.function_call = {"name": ..., "arguments": {...}} (arguments - объект или JSON-строка).

Другие провайдеры (OpenRouter, Groq, OpenAI): ключ уходит как Bearer, функции передаются как tools.
"""
import asyncio
import base64
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional, Union

import httpx

from app.core.config import settings

logger = logging.getLogger("cardioflow.agent.llm")

_TOKEN_SKEW_MS = 60_000  # обновляем токен за минуту до истечения
_DEFAULT_TOKEN_TTL_MS = 29 * 60_000


class LLMError(RuntimeError):
    """Ошибка обращения к LLM (сеть, авторизация, неожиданный формат ответа)."""


@dataclass
class LLMReply:
    content: str = ""
    function_name: Optional[str] = None
    function_args: dict[str, Any] = field(default_factory=dict)
    finish_reason: Optional[str] = None


def llm_enabled() -> bool:
    return bool(settings.llm_api_key.strip())


def parse_json_object(raw: Any) -> dict[str, Any]:
    """Достает объект из arguments: dict, JSON-строка, JSON в ```-блоке или с мусором вокруг."""
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return {}
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE).strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return {}
        try:
            value = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}
    return value if isinstance(value, dict) else {}


def parse_reply(data: dict[str, Any]) -> LLMReply:
    """Разбирает ответ chat/completions в обоих форматах (function_call GigaChat и tool_calls OpenAI)."""
    try:
        choice = data["choices"][0]
        message = choice.get("message") or {}
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise LLMError(f"Неожиданный формат ответа LLM: {str(data)[:300]}") from exc

    reply = LLMReply(content=str(message.get("content") or ""), finish_reason=choice.get("finish_reason"))

    call = message.get("function_call")
    if not call:
        tool_calls = message.get("tool_calls") or []
        if tool_calls and isinstance(tool_calls[0], dict):
            call = tool_calls[0].get("function")
    if isinstance(call, dict) and call.get("name"):
        reply.function_name = str(call["name"])
        reply.function_args = parse_json_object(call.get("arguments"))
        return reply

    # Модель иногда отвечает вызовом функции обычным текстом: {"name": "...", "arguments": {...}}
    embedded = parse_json_object(reply.content)
    if isinstance(embedded.get("name"), str) and "arguments" in embedded:
        reply.function_name = embedded["name"]
        reply.function_args = parse_json_object(embedded.get("arguments"))
    return reply


class LLMClient:
    def __init__(self) -> None:
        self._token: str = ""
        self._expires_at_ms: float = 0.0
        self._lock = asyncio.Lock()

    # ----- настройки -----
    @property
    def is_gigachat(self) -> bool:
        provider = settings.llm_provider.lower()
        if provider in ("gigachat", "giga"):
            return True
        if provider == "openai":
            return False
        hint = f"{settings.llm_base_url} {settings.llm_model_name}".lower()
        return "giga" in hint or "sberbank" in hint

    @staticmethod
    def _verify() -> Union[bool, str]:
        if settings.llm_ca_bundle.strip():
            return settings.llm_ca_bundle.strip()
        return bool(settings.llm_verify_ssl)

    def _http(self, timeout: Optional[float] = None) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=timeout or settings.llm_timeout, verify=self._verify())

    # ----- авторизация -----
    @staticmethod
    def _authorization_key() -> str:
        key = settings.llm_api_key.strip()
        if key.lower().startswith("basic "):
            key = key[6:].strip()
        if ":" in key:  # сырая пара client_id:client_secret -> base64
            key = base64.b64encode(key.encode("utf-8")).decode("ascii")
        return key

    async def _access_token(self, force: bool = False) -> str:
        key = settings.llm_api_key.strip()
        if key.lower().startswith("bearer "):  # готовый access token
            return key[7:].strip()
        if not self.is_gigachat:
            return key
        async with self._lock:
            if not force and self._token and time.time() * 1000 < self._expires_at_ms - _TOKEN_SKEW_MS:
                return self._token
            headers = {
                "Authorization": f"Basic {self._authorization_key()}",
                "RqUID": str(uuid.uuid4()),
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            }
            try:
                async with self._http() as client:
                    response = await client.post(settings.llm_auth_url, headers=headers, data={"scope": settings.llm_scope})
                    response.raise_for_status()
                    data = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise LLMError(f"Не удалось получить токен GigaChat: {exc}") from exc
            token = data.get("access_token")
            if not token:
                raise LLMError("GigaChat не вернул access_token")
            self._token = str(token)
            expires_at = data.get("expires_at")  # миллисекунды Unix-времени
            self._expires_at_ms = float(expires_at) if expires_at else time.time() * 1000 + _DEFAULT_TOKEN_TTL_MS
            return self._token

    # ----- запрос -----
    def _payload(
        self, messages: list[dict[str, Any]], functions: Optional[list[dict[str, Any]]], temperature: float
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": settings.llm_model_name,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if functions:
            if self.is_gigachat:
                payload["functions"] = functions
                payload["function_call"] = "auto"
            else:
                payload["tools"] = [{"type": "function", "function": spec} for spec in functions]
                payload["tool_choice"] = "auto"
        return payload

    async def chat(
        self,
        messages: list[dict[str, Any]],
        functions: Optional[list[dict[str, Any]]] = None,
        temperature: float = 0.1,
    ) -> LLMReply:
        url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
        payload = self._payload(messages, functions, temperature)
        last_error: Optional[Exception] = None
        for attempt in range(2):
            token = await self._access_token(force=attempt > 0 and isinstance(last_error, _Unauthorized))
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json"}
            try:
                async with self._http() as client:
                    response = await client.post(url, headers=headers, json=payload)
                if response.status_code == 401:
                    raise _Unauthorized("LLM ответил 401: токен недействителен")
                response.raise_for_status()
                return parse_reply(response.json())
            except _Unauthorized as exc:
                last_error = exc  # один повтор с новым токеном
            except (httpx.HTTPError, ValueError) as exc:
                raise LLMError(f"Ошибка запроса к LLM: {exc}") from exc
        raise LLMError(str(last_error))


class _Unauthorized(Exception):
    pass


llm_client = LLMClient()
