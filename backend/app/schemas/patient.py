import datetime as dt
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict


class TreatmentPlan(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    patient_id: uuid.UUID
    full_name: str
    doctor_name: str
    prescribed_medication: Optional[str] = None
    frequency_per_day: int
    target_systolic: int
    target_diastolic: int
    morning_time: Optional[dt.time] = None
    evening_time: Optional[dt.time] = None


class LatestMeasurement(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    systolic: Optional[int] = None
    diastolic: Optional[int] = None
    pulse: Optional[int] = None
    risk_status: str
    timestamp: dt.datetime


class MeasurementOut(BaseModel):
    """Замер для графика на главной (время naive, в часовом поясе пациентов, как в событии WebSocket)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    systolic: Optional[int] = None
    diastolic: Optional[int] = None
    pulse: Optional[int] = None
    risk_status: str
    timestamp: dt.datetime


class ScheduleUpdate(BaseModel):
    patient_id: uuid.UUID
    morning_time: dt.time
    evening_time: dt.time


class ScheduleResponse(BaseModel):
    status: str = "validated_and_saved"
