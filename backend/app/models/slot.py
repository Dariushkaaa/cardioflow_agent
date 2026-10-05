import datetime as dt
import uuid
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Uuid, false
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AppointmentSlot(Base):
    __tablename__ = "appointment_slots"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    doctor_id: Mapped[str] = mapped_column(String(100))
    doctor_name: Mapped[str] = mapped_column(String(255))
    # Время слота хранится в UTC (naive datetime), в API отдается с суффиксом Z
    datetime: Mapped[dt.datetime] = mapped_column(DateTime)
    is_booked: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    patient_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("patients.id", ondelete="SET NULL"), nullable=True
    )
