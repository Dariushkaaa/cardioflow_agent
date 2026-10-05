import datetime as dt
import uuid
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MedicationAdherenceLog(Base):
    __tablename__ = "medication_adherence_logs"
    __table_args__ = (
        UniqueConstraint("patient_id", "date", "session_type", name="uq_adherence_patient_date_session"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("patients.id", ondelete="CASCADE"))
    date: Mapped[dt.date] = mapped_column(Date)
    # 'morning', 'evening'
    session_type: Mapped[str] = mapped_column(String(10))
    # 'pending', 'reminded', 'completed', 'missed'
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime)
    is_taken: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    skip_reason: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    raw_complaint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
