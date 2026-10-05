from app.schemas.patient_report import PatientResponseModel
from app.schemas.request import AgentProcessRequest


def test_patient_report_defaults_and_validation():
    x = PatientResponseModel(medication_taken=True, intent="bad")
    assert x.intent == "general_chat"
    assert x.systolic is None


def test_medication_taken_is_optional():
    assert PatientResponseModel(intent="general_chat").medication_taken is None


def test_skip_reason_normalized():
    x = PatientResponseModel(medication_taken=False, skip_reason="unknown", intent="report_data")
    assert x.skip_reason == "other"


def test_request_accepts_backend_format():
    """Backend шлет {"patient_id", "text", "event_type"}; JWT приходит в заголовке."""
    r = AgentProcessRequest(**{"patient_id": "p1", "text": "Давление 120/80", "event_type": "user_message"})
    assert r.message == "Давление 120/80"
    assert r.jwt_token is None


def test_request_accepts_native_format():
    r = AgentProcessRequest(patient_id="p1", jwt_token="t", message="привет")
    assert r.message == "привет"
