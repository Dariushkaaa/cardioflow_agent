"""Фиксация приема/пропуска таблетки по отчету агента."""
import datetime as dt
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.adherence import MedicationAdherenceLog
from app.models.patient import Patient

OPEN_STATUSES = ("pending", "reminded")


def _closest_session_type(patient: Patient, now: dt.datetime) -> str:
    def minutes(t: dt.time) -> int:
        return t.hour * 60 + t.minute

    current = minutes(now.time())

    def distance(t: dt.time) -> int:
        d = abs(current - minutes(t))
        return min(d, 24 * 60 - d)

    return "morning" if distance(patient.morning_time) <= distance(patient.evening_time) else "evening"


async def register_medication_report(
    db: AsyncSession,
    patient: Patient,
    now: dt.datetime,
    medication_taken: bool,
    skip_reason: Optional[str],
    raw_complaint: Optional[str],
) -> MedicationAdherenceLog:
    """Закрывает активный сеанс (pending/reminded) либо создает/обновляет сеанс за сегодня."""
    log = await db.scalar(
        select(MedicationAdherenceLog)
        .where(
            MedicationAdherenceLog.patient_id == patient.id,
            MedicationAdherenceLog.status.in_(OPEN_STATUSES),
        )
        .order_by(MedicationAdherenceLog.expires_at.desc())
        .limit(1)
    )
    if log is None:
        session_type = _closest_session_type(patient, now)
        log = await db.scalar(
            select(MedicationAdherenceLog).where(
                MedicationAdherenceLog.patient_id == patient.id,
                MedicationAdherenceLog.date == now.date(),
                MedicationAdherenceLog.session_type == session_type,
            )
        )
        if log is None:
            log = MedicationAdherenceLog(
                patient_id=patient.id,
                date=now.date(),
                session_type=session_type,
                expires_at=now,
            )
            db.add(log)

    log.status = "completed"
    log.is_taken = medication_taken
    log.skip_reason = skip_reason
    log.raw_complaint = raw_complaint
    return log
