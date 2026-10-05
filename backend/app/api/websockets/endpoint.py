import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.api.websockets.manager import manager
from app.core.security import WS_4008_POLICY_VIOLATION, authenticate_ws_token, create_access_token
from app.services import agent_client

logger = logging.getLogger(__name__)
router = APIRouter()


async def _handle_chat_message(
    patient_id: str, text: str, event_type: str = agent_client.EVENT_USER_MESSAGE
) -> None:
    """Передает реплику пациента в Agent Service и транслирует ответ обратно в сокет."""
    try:
        # Токен из URL сокета может истечь, пока соединение живо (сокет проверяется один раз при
        # подключении). Пациент уже аутентифицирован, поэтому для агента выпускаем свежий токен.
        agent_token = create_access_token(uuid.UUID(patient_id))
        data = await agent_client.process_message(patient_id, text, agent_token, event_type)
    except Exception:
        logger.exception("Agent Service недоступен или вернул ошибку")
        await manager.send_event(
            patient_id, "agent_message", {"text": agent_client.FALLBACK_TEXT, "quick_replies": []}
        )
        return

    await manager.send_event(patient_id, "agent_message", agent_client.normalize_reply(data))

    # Агент может вернуть и дополнительные события для интерфейса
    extra_events = data.get("events")
    if isinstance(extra_events, list):
        for item in extra_events:
            if isinstance(item, dict) and item.get("event"):
                await manager.send_event(patient_id, str(item["event"]), item.get("data") or {})


@router.websocket("/ws/patient/{patient_id}")
async def patient_websocket(
    websocket: WebSocket,
    patient_id: str,
    token: Optional[str] = Query(default=None),
) -> None:
    await websocket.accept()

    authenticated_id = authenticate_ws_token(token, patient_id) if token else None
    if authenticated_id is None:
        await websocket.close(code=WS_4008_POLICY_VIOLATION)
        return

    pid = str(authenticated_id)
    manager.register(pid, websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
                action = message.get("action")
                data = message.get("data") or {}
            except (json.JSONDecodeError, AttributeError):
                await websocket.send_json({"event": "error", "data": {"message": "Некорректный JSON"}})
                continue

            if action == "send_message":
                text = str(data.get("text", "")).strip()
                if not text:
                    continue
                manager.spawn(_handle_chat_message(pid, text))
            elif action == "init_onboarding":
                # Приветствие агента с назначениями врача (по запросу интерфейса)
                manager.spawn(_handle_chat_message(pid, "", agent_client.EVENT_INIT_ONBOARDING))
            else:
                await websocket.send_json(
                    {"event": "error", "data": {"message": f"Неизвестное действие: {action}"}}
                )
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(pid, websocket)
