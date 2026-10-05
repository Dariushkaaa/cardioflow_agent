"""Три жестко поддерживаемых сценария диалога (см. SCENARIOS.md).

Тесты проходят через настоящий граф агента (nlu -> report -> clarify -> slots ...), а REST API бэкенда
заменен fake-клиентом с теми же порогами риска, что и у Risk Engine бэкенда. LLM не нужен (режим правил).
"""
import asyncio
import json
from contextlib import contextmanager
from unittest import mock

from app.core.config import settings
from app.graph.workflow import workflow
from app.tools.backend_client import backend_client

TOKEN = "test-token"
PATIENT = "d3b07384-d113-4ec6-a563-9a3d46532401"

PLAN = {
    "patient_id": PATIENT,
    "full_name": "Иванов Иван Иванович",
    "doctor_name": "Петров А.С.",
    "prescribed_medication": "Лозартан 50 мг",
    "frequency_per_day": 2,
    "target_systolic": 130,
    "target_diastolic": 80,
    "morning_time": "08:00:00",
    "evening_time": "20:00:00",
}
SLOTS = [
    {"id": "s1", "doctor_name": "Петров А.С.", "datetime": "2030-01-10T07:00:00Z"},
    {"id": "s2", "doctor_name": "Петров А.С.", "datetime": "2030-01-10T08:30:00Z"},
    {"id": "s3", "doctor_name": "Сидорова Е.В.", "datetime": "2030-01-11T09:00:00Z"},
]


def _risk(sys_, dia, pulse):
    levels = []
    if sys_ is not None and dia is not None:
        if sys_ >= 160 or dia >= 100 or sys_ < 90 or dia < 60:
            levels.append(2)
        elif sys_ >= 140 or dia >= 90:
            levels.append(1)
        else:
            levels.append(0)
    if pulse is not None:
        levels.append(2 if pulse < 40 or pulse > 130 else 1 if pulse < 50 or pulse > 100 else 0)
    return ["stable", "warning", "critical"][max(levels)] if levels else None


class FakeBackend:
    """Те же контракты, что у REST API бэкенда: /patient/treatment-plan, /reports/, /slots/available."""

    def __init__(self):
        self.measurements = []
        self.reports = []
        self.slot_calls = 0

    async def get_treatment_plan(self, patient_id, token):
        return dict(PLAN)

    async def get_latest_measurement(self, token):
        return self.measurements[-1] if self.measurements else None

    async def submit_patient_report(self, report, token):
        self.reports.append(report)
        level = _risk(report.get("systolic"), report.get("diastolic"), report.get("pulse"))
        if level:
            self.measurements.append(
                {"systolic": report.get("systolic"), "diastolic": report.get("diastolic"), "pulse": report.get("pulse"), "risk_status": level}
            )
        action = "book_appointment" if level == "critical" or report.get("skip_reason") == "side_effects" else (
            "repeat_measurement" if level == "warning" else "none"
        )
        return {"status": "success", "risk_level": level or "unknown", "action_required": action, "message": "ok"}

    async def search_available_slots(self, token, limit=3):
        self.slot_calls += 1
        return SLOTS[:limit]


@contextmanager
def dialog():
    fake = FakeBackend()
    with mock.patch.object(backend_client, "get_treatment_plan", fake.get_treatment_plan), \
         mock.patch.object(backend_client, "get_latest_measurement", fake.get_latest_measurement), \
         mock.patch.object(backend_client, "submit_patient_report", fake.submit_patient_report), \
         mock.patch.object(backend_client, "search_available_slots", fake.search_available_slots), \
         mock.patch.object(settings, "llm_api_key", ""), \
         mock.patch.object(settings, "timezone", "UTC"):
        yield fake


def say(text, event_type="user_message"):
    result = asyncio.run(
        workflow.ainvoke(
            {
                "patient_id": PATIENT,
                "jwt_token": TOKEN,
                "messages": [{"role": "user", "content": text}],
                "event_type": event_type,
                "response_text": "",
                "quick_replies": [],
                "events": [],
            }
        )
    )
    return result


def test_scenario_1_stable():
    with dialog() as backend:
        hello = say("", "init_onboarding")
        assert "Петров А.С." in hello["response_text"] and "Лозартан" in hello["response_text"]

        greet = say("Привет")
        assert "Мой план лечения" in greet["quick_replies"]

        plan = say("Мой план лечения")
        assert "Лозартан 50 мг" in plan["response_text"] and "130/80" in plan["response_text"]

        saved = say("120/80, 70")
        assert backend.reports[-1]["systolic"] == 120 and backend.reports[-1]["diastolic"] == 80
        assert backend.reports[-1]["pulse"] == 70
        assert saved["risk_level"] == "stable"
        assert "120/80" in saved["response_text"] and "stable" in saved["response_text"]
        assert not saved.get("events")

        advice = say("Какие у вас рекомендации по питанию и сколько соли можно?")
        assert "соль" in advice["response_text"].lower() or "соли" in advice["response_text"].lower()
        assert "CardioFlow" in advice["response_text"]


def test_scenario_2_warning_then_improvement():
    with dialog() as backend:
        warn = say("Давление 150/95")
        assert warn["risk_level"] == "warning" and warn["action_required"] == "repeat_measurement"
        assert "warning" in warn["response_text"]
        assert "20 минут" in warn["response_text"]
        assert backend.slot_calls == 0  # запись к врачу при warning не предлагается

        better = say("Перемерил: 135/85")
        assert better["risk_level"] == "stable"
        text = better["response_text"]
        assert "150/95" in text and "135/85" in text  # было / стало
        assert "улучшилось" in text and "молодец" in text


def test_scenario_3_critical_escalation_and_booking():
    with dialog() as backend:
        crit = say("Давление 170/105, меня тошнит, пропустил таблетку")
        report = backend.reports[-1]
        assert (report["systolic"], report["diastolic"]) == (170, 105)
        assert report["medication_taken"] is False and report["skip_reason"] == "side_effects"
        assert crit["risk_level"] == "critical" and crit["action_required"] == "book_appointment"
        assert "critical" in crit["response_text"]
        assert "не отменяйте терапию" in crit["response_text"]
        # свободные слоты врача в тексте; событие show_appointment_slots шлет backend при POST /reports/
        assert backend.slot_calls == 1 and len(crit["available_slots"]) == 3
        assert "Петров А.С." in crit["response_text"]
        assert not crit.get("events")  # дубль события не нужен

        booked = say(
            json.dumps({"doctor_name": "Петров А.С.", "datetime": "2030-01-10T07:00:00Z"}, ensure_ascii=False),
            "appointment_booked",
        )
        text = booked["response_text"]
        assert "записаны" in text and "10.01 07:00" in text
        assert "гипертоническом кризе" in text and "103" in text and "не принимайте дополнительные таблетки" in text.lower()


def test_patient_can_ask_for_slots_directly():
    with dialog():
        result = say("Хочу записаться к врачу")
        assert len(result["available_slots"]) == 3
        assert result["events"] == [{"event": "show_appointment_slots", "data": {"reason": "patient_request"}}]


def test_fallback_parses_pulse_after_pressure():
    from app.graph.nodes import _fallback_parse

    x = _fallback_parse("120/80, 70")
    assert (x.systolic, x.diastolic, x.pulse) == (120, 80, 70)
    y = _fallback_parse("Давление 135/85 в 21:30")
    assert (y.systolic, y.diastolic, y.pulse) == (135, 85, None)
