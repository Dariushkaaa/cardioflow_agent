"""Валидатор интервала между утренним и вечерним приемом лекарств (8-12 часов)."""
import datetime as dt

MIN_INTERVAL_HOURS = 8
MAX_INTERVAL_HOURS = 12


class ScheduleValidationError(ValueError):
    pass


def interval_minutes(morning: dt.time, evening: dt.time) -> int:
    """Количество минут от утреннего приема до вечернего (с переходом через полночь)."""
    morning_min = morning.hour * 60 + morning.minute
    evening_min = evening.hour * 60 + evening.minute
    return (evening_min - morning_min) % (24 * 60)


def validate_schedule(morning: dt.time, evening: dt.time) -> None:
    minutes = interval_minutes(morning, evening)
    if minutes < MIN_INTERVAL_HOURS * 60 or minutes > MAX_INTERVAL_HOURS * 60:
        hours = minutes / 60
        raise ScheduleValidationError(
            f"Интервал между приемами должен быть от {MIN_INTERVAL_HOURS} до "
            f"{MAX_INTERVAL_HOURS} часов, сейчас: {hours:.1f} ч"
        )
