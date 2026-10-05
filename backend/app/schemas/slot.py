import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, field_serializer


def _to_utc_z(value: dt.datetime) -> str:
    """Naive-время слота трактуется как UTC и отдается в формате 2026-06-07T10:00:00Z."""
    if value.tzinfo is not None:
        value = value.astimezone(dt.timezone.utc).replace(tzinfo=None)
    return value.replace(microsecond=0).isoformat() + "Z"


class SlotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    doctor_name: str
    datetime: dt.datetime

    @field_serializer("datetime")
    def serialize_datetime(self, value: dt.datetime) -> str:
        return _to_utc_z(value)


class SlotsResponse(BaseModel):
    slots: list[SlotOut]


class BookRequest(BaseModel):
    patient_id: uuid.UUID
    slot_id: uuid.UUID


class BookResponse(BaseModel):
    status: str
    slot_id: uuid.UUID
    datetime: dt.datetime

    @field_serializer("datetime")
    def serialize_datetime(self, value: dt.datetime) -> str:
        return _to_utc_z(value)
