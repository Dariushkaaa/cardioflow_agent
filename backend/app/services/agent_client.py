"""HTTPx-клиент для проксирования реплик пациента в Agent Service.

Контракт с Agent Service:
  POST AGENT_SERVICE_URL  (по умолчанию http://agent:8001/api/v1/agent/process)
  Header: Authorization: Bearer <JWT пациента>
  Body:   {"patient_id": "<uuid>", "text": "<реплика пациента>", "event_type": "user_message"}
          event_type = "init_onboarding" запрашивает приветствие с назначениями врача;
          event_type = "appointment_booked" сообщает о записи к врачу (агент напоминает правила при кризе).
  Ответ:  {"text": "...", "reply_text": "...", "quick_replies": ["...", "..."], "action_required": "..."}
          (допустимы ключи text / reply_text / reply / message); необязательный "events": [{"event", "data"}]
          транслируется в сокет как есть
"""
from typing import Any

import httpx

from app.core.config import settings

FALLBACK_TEXT = "Сейчас я не могу ответить. Пожалуйста, попробуйте написать чуть позже."

EVENT_USER_MESSAGE = "user_message"
EVENT_INIT_ONBOARDING = "init_onboarding"
EVENT_APPOINTMENT_BOOKED = "appointment_booked"  # text = JSON {"doctor_name", "datetime"}


async def process_message(
    patient_id: str, text: str, token: str, event_type: str = EVENT_USER_MESSAGE
) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"patient_id": patient_id, "text": text, "event_type": event_type}
    async with httpx.AsyncClient(timeout=settings.AGENT_TIMEOUT_SECONDS) as client:
        response = await client.post(settings.AGENT_SERVICE_URL, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
    return data if isinstance(data, dict) else {"text": str(data)}


def normalize_reply(data: dict[str, Any]) -> dict[str, Any]:
    """Приводит ответ агента к формату data события agent_message."""
    text = data.get("text") or data.get("reply_text") or data.get("reply") or data.get("message") or ""
    quick_replies = data.get("quick_replies") or []
    if not isinstance(quick_replies, list):
        quick_replies = []
    return {"text": str(text), "quick_replies": [str(q) for q in quick_replies]}
