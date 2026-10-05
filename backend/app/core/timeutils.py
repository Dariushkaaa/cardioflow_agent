from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.config import settings


def now_local() -> datetime:
    """Текущее время в часовом поясе пациентов (naive datetime, как хранится в БД)."""
    try:
        return datetime.now(ZoneInfo(settings.TIMEZONE)).replace(tzinfo=None)
    except ZoneInfoNotFoundError:
        return datetime.now()


def utcnow() -> datetime:
    """Текущее время UTC (naive datetime). Используется для слотов записи."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
