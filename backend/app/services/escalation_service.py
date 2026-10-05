"""Логика уровней эскалации и окон тишины.

Функции работают с БД, но не отправляют сообщения сами: возвращают список Notification,
которые воркер доставляет через WebSocket Manager.
"""
import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.adherence import MedicationAdherenceLog
from app.models.patient import Patient

OPEN_STATUSES = ("pending", "reminded")
NO_DATA_TEXT = "нет данных за день"


@dataclass
class Notification:
    patient_id: str
    event: str
    data: dict[str, Any] = field(default_factory=dict)


def agent_message(patient_id: Any, text: str, quick_replies: Optional[list[str]] = None) -> Notification:
    return Notification(
        patient_id=str(patient_id),
        event="agent_message",
        data={"text": text, "quick_replies": quick_replies or []},
    )


def is_quiet_time(current: dt.time, start: dt.time, end: dt.time) -> bool:
    """Окно тишины, в т.ч. с переходом через полночь (22:00-08:00)."""
    if start <= end:
        return start <= current < end
    return current >= start or current < end


async def create_scheduled_sessions(db: AsyncSession, now: dt.datetime) -> list[Notification]:
    """Создает сеансы приема по расписанию (pending, дедлайн +2 часа) и плановые напоминания."""
    notifications: list[Notification] = []
    today = now.date()
    window = dt.timedelta(hours=settings.SESSION_DEADLINE_HOURS)

    patients = (await db.execute(select(Patient))).scalars().all()
    for patient in patients:
        for session_type, scheduled in (("morning", patient.morning_time), ("evening", patient.evening_time)):
            start = dt.datetime.combine(today, scheduled)
            if not (start <= now < start + window):
                continue
            exists = await db.scalar(
                select(MedicationAdherenceLog.id).where(
                    MedicationAdherenceLog.patient_id == patient.id,
                    MedicationAdherenceLog.date == today,
                    MedicationAdherenceLog.session_type == session_type,
                )
            )
            if exists:
                continue
            db.add(
                MedicationAdherenceLog(
                    patient_id=patient.id,
                    date=today,
                    session_type=session_type,
                    status="pending",
                    expires_at=now + window,
                )
            )
            when = "утренний" if session_type == "morning" else "вечерний"
            medication = f" ({patient.prescribed_medication})" if patient.prescribed_medication else ""
            notifications.append(
                agent_message(
                    patient.id,
                    f"Пора принять {when} прием лекарства{medication}. "
                    "Если есть тонометр, пришлите, пожалуйста, давление и расскажите о самочувствии.",
                    ["Принял(а) лекарство", "Пропустил(а)", "Плохо себя чувствую"],
                )
            )
    await db.commit()
    return notifications


async def send_soft_reminders(db: AsyncSession, now: dt.datetime) -> list[Notification]:
    """Уровень 1: мягкое напоминание через +2 часа, с учетом окна тишины."""
    notifications: list[Notification] = []
    rows = (
        await db.execute(
            select(MedicationAdherenceLog, Patient)
            .join(Patient, Patient.id == MedicationAdherenceLog.patient_id)
            .where(
                MedicationAdherenceLog.status == "pending",
                MedicationAdherenceLog.expires_at <= now,
            )
        )
    ).all()
    for log, patient in rows:
        if is_quiet_time(now.time(), patient.quiet_hours_start, patient.quiet_hours_end):
            continue  # отправка блокируется до конца окна тишины (08:00)
        log.status = "reminded"
        notifications.append(
            agent_message(
                patient.id,
                "Напоминаю о приеме лекарства. Если вы уже приняли таблетку, просто напишите мне, "
                "а если что-то беспокоит, расскажите, я рядом.",
                ["Уже принял(а)", "Пока не принял(а)", "Плохо себя чувствую"],
            )
        )
    await db.commit()
    return notifications


async def close_day(db: AsyncSession, now: dt.datetime) -> list[Notification]:
    """Уровень 2: итог дня. Затем проверка уровня 3 (потеря контакта)."""
    notifications: list[Notification] = []
    today = now.date()

    # Хвосты прошлых дней, которые так и остались открытыми, считаем пропусками
    stale = (
        await db.execute(
            select(MedicationAdherenceLog).where(
                MedicationAdherenceLog.date < today,
                MedicationAdherenceLog.status.in_(OPEN_STATUSES),
            )
        )
    ).scalars().all()
    for log in stale:
        _mark_missed(log)

    patients = (await db.execute(select(Patient))).scalars().all()
    for patient in patients:
        logs = (
            await db.execute(
                select(MedicationAdherenceLog).where(
                    MedicationAdherenceLog.patient_id == patient.id,
                    MedicationAdherenceLog.date == today,
                )
            )
        ).scalars().all()
        types = {log.session_type for log in logs}
        if {"morning", "evening"} <= types and all(log.status in OPEN_STATUSES for log in logs):
            for log in logs:
                _mark_missed(log)
            notifications.append(
                agent_message(
                    patient.id,
                    "Сегодня от вас не было данных о приеме лекарств и самочувствии. "
                    "Завтра продолжим, а если вы плохо себя чувствуете, напишите мне в любое время.",
                    ["Я в порядке", "Плохо себя чувствую"],
                )
            )
    await db.commit()

    notifications.extend(await check_lost_to_follow_up(db))
    return notifications


def _mark_missed(log: MedicationAdherenceLog) -> None:
    log.status = "missed"
    log.skip_reason = "no_data"
    log.raw_complaint = NO_DATA_TEXT


async def check_lost_to_follow_up(db: AsyncSession) -> list[Notification]:
    """Уровень 3: 4 и более последовательных сеанса missed -> lost_to_follow_up."""
    notifications: list[Notification] = []
    threshold = settings.LOST_AFTER_MISSED_SESSIONS
    patients = (await db.execute(select(Patient).where(Patient.status == "active"))).scalars().all()
    for patient in patients:
        statuses = (
            await db.execute(
                select(MedicationAdherenceLog.status)
                .where(MedicationAdherenceLog.patient_id == patient.id)
                .order_by(MedicationAdherenceLog.date.desc(), MedicationAdherenceLog.expires_at.desc())
                .limit(threshold)
            )
        ).scalars().all()
        if len(statuses) == threshold and all(s == "missed" for s in statuses):
            patient.status = "lost_to_follow_up"
            notifications.append(
                Notification(
                    patient_id=str(patient.id),
                    event="patient_status_update",
                    data={"status": "lost_to_follow_up"},
                )
            )
    await db.commit()
    return notifications
