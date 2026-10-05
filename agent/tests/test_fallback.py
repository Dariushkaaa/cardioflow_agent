from app.graph.nodes import _fallback_parse, has_report_data


def test_fallback_bp():
    x = _fallback_parse("Давление 160/100, пульс 85, таблетку не принял")
    assert (x.systolic, x.diastolic, x.pulse) == (160, 100, 85)
    assert x.medication_taken is False


def test_bp_only_does_not_claim_medication():
    x = _fallback_parse("Давление 120/80")
    assert (x.systolic, x.diastolic) == (120, 80)
    assert x.medication_taken is None
    assert x.skip_reason is None


def test_random_numbers_are_not_blood_pressure():
    x = _fallback_parse("Мне 65 лет, пульс 70")
    assert x.systolic is None and x.diastolic is None
    assert x.pulse == 70


def test_side_effects_skip_reason():
    x = _fallback_parse("Не принял таблетку, тошнит")
    assert x.medication_taken is False
    assert x.skip_reason == "side_effects"
    assert x.intent == "complain_side_effects"


def test_complaint_without_skip_has_no_skip_reason():
    x = _fallback_parse("Плохо себя чувствую")
    assert x.medication_taken is None
    assert x.skip_reason is None
    assert not has_report_data(x.model_dump())


def test_pending_is_not_a_skip():
    x = _fallback_parse("Пока не принял(а)")
    assert x.medication_taken is None


def test_taken_quick_reply():
    assert _fallback_parse("Принял(а) лекарство").medication_taken is True
    assert _fallback_parse("Уже принял(а)").medication_taken is True


def test_greeting_is_general_chat():
    x = _fallback_parse("Привет")
    assert x.intent == "general_chat"
    assert not has_report_data(x.model_dump())
