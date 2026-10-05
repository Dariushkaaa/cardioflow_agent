from typing import Optional

from pydantic import BaseModel, Field, field_validator


class PatientResponseModel(BaseModel):
    systolic: Optional[int] = Field(None, description="Систолическое давление")
    diastolic: Optional[int] = Field(None, description="Диастолическое давление")
    pulse: Optional[int] = Field(None, description="Пульс")
    medication_taken: Optional[bool] = Field(
        None, description="Принял ли пациент препарат; null, если о препарате речи не было"
    )
    skip_reason: Optional[str] = Field(None, description="forgot, side_effects, late, other")
    raw_complaint: Optional[str] = None
    intent: str = Field(
        "general_chat",
        description="report_data, ask_advice, complain_side_effects, escalation_reply, request_slots, show_plan, general_chat",
    )

    @field_validator("skip_reason")
    @classmethod
    def validate_skip_reason(cls, value):
        if value is not None and value not in {"forgot", "side_effects", "late", "other"}:
            return "other"
        return value

    @field_validator("intent")
    @classmethod
    def validate_intent(cls, value):
        allowed = {
            "report_data",
            "ask_advice",
            "complain_side_effects",
            "escalation_reply",
            "request_slots",
            "show_plan",
            "general_chat",
        }
        return value if value in allowed else "general_chat"
