from typing import Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class AgentProcessRequest(BaseModel):
    """Запрос к агенту.

    Принимает два формата:
      - собственный:        {"patient_id", "jwt_token", "message", "event_type"}
      - формат бэкенда:     {"patient_id", "text", "event_type"} + JWT в заголовке Authorization
    """

    model_config = ConfigDict(populate_by_name=True)

    patient_id: str = Field(min_length=1)
    jwt_token: Optional[str] = None
    message: str = Field(default="", max_length=10000, validation_alias=AliasChoices("message", "text"))
    event_type: str = "user_message"


class AgentProcessResponse(BaseModel):
    reply_text: str
    # Дубль reply_text: именно это поле читает backend (agent_client.normalize_reply)
    text: str = ""
    quick_replies: list[str] = []
    action_required: Optional[str] = None
    # Дополнительные события интерфейса: [{"event": "show_appointment_slots", "data": {...}}]
    events: list[dict] = []
