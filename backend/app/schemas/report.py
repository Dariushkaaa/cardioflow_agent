import uuid
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class ReportCreate(BaseModel):
    """Структурированный отчет агента после NLU-анализа реплики пациента.

    Поля давления опциональны: можно зафиксировать только факт приема/пропуска таблетки.
    """

    patient_id: uuid.UUID
    systolic: Optional[int] = Field(default=None, ge=40, le=300)
    diastolic: Optional[int] = Field(default=None, ge=20, le=200)
    pulse: Optional[int] = Field(default=None, ge=20, le=250)
    medication_taken: Optional[bool] = None
    skip_reason: Optional[str] = Field(default=None, max_length=50)
    raw_complaint: Optional[str] = None

    @model_validator(mode="after")
    def check_systolic_and_diastolic_together(self):
        if (self.systolic is None) != (self.diastolic is None):
            raise ValueError("systolic и diastolic должны передаваться вместе")
        return self


class ReportResponse(BaseModel):
    status: str
    risk_level: str
    action_required: str
    message: str
