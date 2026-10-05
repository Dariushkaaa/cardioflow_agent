"""Детерминированная оценка рисков по АД и пульсу.

Чистые функции без зависимостей от БД, сторонних API и LLM.

Пороги (в спецификации не заданы, приняты разумные значения):
  critical: САД >= 160 или ДАД >= 100, либо САД < 90 или ДАД < 60, пульс < 40 или > 130
  warning:  САД >= целевое + 10 или ДАД >= целевое + 10 (при целях 130/80 это 140/90),
            пульс < 50 или > 100
  stable:   всё остальное
"""
from typing import Optional

STABLE = "stable"
WARNING = "warning"
CRITICAL = "critical"

ACTION_NONE = "none"
ACTION_REPEAT_MEASUREMENT = "repeat_measurement"
ACTION_BOOK_APPOINTMENT = "book_appointment"

SKIP_REASON_SIDE_EFFECTS = "side_effects"

_ORDER = {STABLE: 0, WARNING: 1, CRITICAL: 2}


def _worst(*levels: Optional[str]) -> Optional[str]:
    known = [lvl for lvl in levels if lvl is not None]
    if not known:
        return None
    return max(known, key=lambda lvl: _ORDER[lvl])


def assess_blood_pressure(
    systolic: Optional[int],
    diastolic: Optional[int],
    target_systolic: int = 130,
    target_diastolic: int = 80,
) -> Optional[str]:
    if systolic is None or diastolic is None:
        return None
    if systolic >= 160 or diastolic >= 100 or systolic < 90 or diastolic < 60:
        return CRITICAL
    if systolic >= target_systolic + 10 or diastolic >= target_diastolic + 10:
        return WARNING
    return STABLE


def assess_pulse(pulse: Optional[int]) -> Optional[str]:
    if pulse is None:
        return None
    if pulse < 40 or pulse > 130:
        return CRITICAL
    if pulse < 50 or pulse > 100:
        return WARNING
    return STABLE


def assess_risk(
    systolic: Optional[int],
    diastolic: Optional[int],
    pulse: Optional[int],
    target_systolic: int = 130,
    target_diastolic: int = 80,
) -> Optional[str]:
    """Итоговый уровень риска; None, если числовых данных нет."""
    return _worst(
        assess_blood_pressure(systolic, diastolic, target_systolic, target_diastolic),
        assess_pulse(pulse),
    )


def decide_action(risk_level: Optional[str], skip_reason: Optional[str]) -> str:
    if risk_level == CRITICAL or skip_reason == SKIP_REASON_SIDE_EFFECTS:
        return ACTION_BOOK_APPOINTMENT
    if risk_level == WARNING:
        return ACTION_REPEAT_MEASUREMENT
    return ACTION_NONE


def build_escalation_reason(
    risk_level: Optional[str], skip_reason: Optional[str], has_blood_pressure: bool = True
) -> str:
    """Причина для события show_appointment_slots, напр. critical_blood_pressure_and_side_effects."""
    parts = []
    subject = "blood_pressure" if has_blood_pressure else "pulse"
    if risk_level == CRITICAL:
        parts.append(f"critical_{subject}")
    elif risk_level == WARNING:
        parts.append(f"elevated_{subject}")
    if skip_reason == SKIP_REASON_SIDE_EFFECTS:
        parts.append("side_effects")
    return "_and_".join(parts) or "doctor_consultation"
