"""Фоновые задачи эскалации (APScheduler).

  - каждую минуту: создание сеансов приема по расписанию (pending, дедлайн +2 часа);
  - каждые 5 минут: уровень 1 (мягкое напоминание, с учетом окна тишины);
  - ежедневно в 22:00: уровень 2 (итог дня) и уровень 3 (потеря контакта).
"""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.api.websockets.manager import manager
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.timeutils import now_local
from app.services import escalation_service as escalation

logger = logging.getLogger(__name__)


async def _dispatch(notifications: list[escalation.Notification]) -> None:
    for note in notifications:
        await manager.send_event(note.patient_id, note.event, note.data)


async def job_create_sessions() -> None:
    try:
        async with SessionLocal() as db:
            await _dispatch(await escalation.create_scheduled_sessions(db, now_local()))
    except Exception:
        logger.exception("Ошибка создания сеансов приема")


async def job_soft_reminders() -> None:
    try:
        async with SessionLocal() as db:
            await _dispatch(await escalation.send_soft_reminders(db, now_local()))
    except Exception:
        logger.exception("Ошибка отправки мягких напоминаний")


async def job_close_day() -> None:
    try:
        async with SessionLocal() as db:
            await _dispatch(await escalation.close_day(db, now_local()))
    except Exception:
        logger.exception("Ошибка подведения итогов дня")


def setup_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.TIMEZONE)
    scheduler.add_job(
        job_create_sessions, "interval", minutes=1, id="create_sessions", max_instances=1, coalesce=True
    )
    scheduler.add_job(
        job_soft_reminders,
        "interval",
        minutes=settings.REMINDER_CHECK_MINUTES,
        id="soft_reminders",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        job_close_day,
        "cron",
        hour=settings.DAILY_SUMMARY_HOUR,
        minute=settings.DAILY_SUMMARY_MINUTE,
        id="close_day",
        max_instances=1,
        coalesce=True,
    )
    return scheduler
