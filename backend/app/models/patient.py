import datetime as dt
import uuid
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Time, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.timeutils import utcnow


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str] = mapped_column(String(255))
    doctor_name: Mapped[str] = mapped_column(String(255))
    target_systolic: Mapped[int] = mapped_column(Integer, default=130, server_default="130")
    target_diastolic: Mapped[int] = mapped_column(Integer, default=80, server_default="80")
    prescribed_medication: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    frequency_per_day: Mapped[int] = mapped_column(Integer, default=2, server_default="2")
    morning_time: Mapped[dt.time] = mapped_column(Time, default=dt.time(9, 0), server_default="09:00:00")
    evening_time: Mapped[dt.time] = mapped_column(Time, default=dt.time(21, 0), server_default="21:00:00")
    # 'active', 'lost_to_follow_up'
    status: Mapped[str] = mapped_column(String(30), default="active", server_default="active")
    quiet_hours_start: Mapped[dt.time] = mapped_column(Time, default=dt.time(22, 0), server_default="22:00:00")
    quiet_hours_end: Mapped[dt.time] = mapped_column(Time, default=dt.time(8, 0), server_default="08:00:00")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, server_default=func.now())
