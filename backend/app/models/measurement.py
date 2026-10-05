import datetime as dt
import uuid
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.timeutils import now_local


class BloodPressureMeasurement(Base):
    __tablename__ = "blood_pressure_measurements"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("patients.id", ondelete="CASCADE"))
    timestamp: Mapped[dt.datetime] = mapped_column(DateTime, default=now_local)
    systolic: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    diastolic: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pulse: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # stable, warning, critical
    risk_status: Mapped[str] = mapped_column(String(20))
