import json
import logging
import re
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.core.prompts import (
    HYPERTENSIVE_CRISIS_RULES,
    REMEASURE_MINUTES,
    SKIP_CONFIRMATION,
    STATUS_TEXT,
    TOOL_PROMPT,
)
from app.llm.client import llm_enabled
from app.llm.tools import digits_in, llm_parse_message
from app.schemas.patient_report import PatientResponseModel
from app.tools.backend_client import backend_client
from app.tools.rag_retriever import retriever

logger = logging.getLogger("cardioflow.agent.nodes")

QUICK_REPLY_SETUP_TIME = "Перейти к настройке времени"
QUICK_REPLY_SHOW_PLAN = "Мой план лечения"
QUICK_REPLY_ADD_BP = "Записать давление"

_NEGATIVE = ("не принял", "не принимал", "не выпил", "не пил", "не пью", "пропустил", "забыл", "отменил")
_POSITIVE = ("принял", "выпил", "приняла", "выпила", "принимал")
_PENDING = ("пока не", "еще не", "ещё не", "позже", "потом", "сейчас приму")
_SIDE = ("тошнит", "тошно", "тошнота", "кружится", "головокруж", "побоч", "плохо", "слабост", "сыпь", "боль")
_ADVICE = ("можно ли", "что делать", "питани", "как правильно", "что лучше", "можно", "рекомендаци", "соль", "соли", "диет")
_PLAN = ("план лечени", "мое лечение", "мое назначение", "мои назначения", "что мне назначил", "какое лекарство", "какой препарат")
_BOOKING_WORDS = ("врач", "прием", "приём", "терапевт", "кардиолог", "консультац")


def _valid_bp(systolic: Optional[int], diastolic: Optional[int]) -> bool:
    return (
        systolic is not None
        and diastolic is not None
        and 40 <= systolic <= 300
        and 20 <= diastolic <= 200
        and systolic > diastolic
    )


def sanitize_report(report: PatientResponseModel) -> PatientResponseModel:
    """Приводит разбор реплики (в т.ч. от LLM) к тому, что примет backend (иначе он ответит 422)."""
    if not _valid_bp(report.systolic, report.diastolic):
        report.systolic = report.diastolic = None
    if report.pulse is not None and not 20 <= report.pulse <= 250:
        report.pulse = None
    if report.medication_taken is not False:
        report.skip_reason = None  # причина пропуска имеет смысл только при пропуске
    return report


def _fallback_parse(message: str) -> PatientResponseModel:
    """Разбор реплики по правилам (когда LLM недоступен): давление, пульс, прием таблетки, жалобы."""
    low = message.lower().replace("ё", "е")

    systolic = diastolic = pulse = None
    m = re.search(r"(\d{2,3})\s*(?:/|\\|на|из)\s*(\d{2,3})", low)
    if not m:
        m = re.search(r"(?:давлени\w*|\bад\b)\D{0,12}?(\d{2,3})[\s,;и]{1,4}(\d{2,3})", low)
    if m:
        systolic, diastolic = int(m.group(1)), int(m.group(2))
    pm = re.search(r"(?:пульс|pulse|чсс)\D{0,10}(\d{2,3})", low) or re.search(r"(\d{2,3})\s*уд", low)
    if pm:
        pulse = int(pm.group(1))
    elif m:
        # «120/80, 70»: число сразу после давления - это пульс
        tail = re.match(r"[\s,;и.]*(\d{2,3})(?![\d:])", low[m.end():])
        if tail:
            pulse = int(tail.group(1))

    pending = any(x in low for x in _PENDING)
    negative = any(x in low for x in _NEGATIVE) and not pending
    positive = any(x in low for x in _POSITIVE) and not any(x in low for x in _NEGATIVE)
    taken: Optional[bool] = False if negative else True if positive else None
    side = any(x in low for x in _SIDE)

    reason = None
    if taken is False:
        if side:
            reason = "side_effects"
        elif "забыл" in low:
            reason = "forgot"
        elif "не успел" in low or "поздно" in low:
            reason = "late"
        else:
            reason = "other"

    has_data = systolic is not None or pulse is not None or taken is not None
    wants_slots = ("записа" in low and any(x in low for x in _BOOKING_WORDS)) or "свободные окна" in low or "свободные слоты" in low
    if side:
        intent = "complain_side_effects"
    elif has_data:
        intent = "report_data"
    elif wants_slots:
        intent = "request_slots"
    elif any(x in low for x in _PLAN):
        intent = "show_plan"
    elif any(x in low for x in _ADVICE):
        intent = "ask_advice"
    else:
        intent = "general_chat"

    return sanitize_report(
        PatientResponseModel(
            systolic=systolic,
            diastolic=diastolic,
            pulse=pulse,
            medication_taken=taken,
            skip_reason=reason,
            raw_complaint=message if side else None,
            intent=intent,
        )
    )


def _merge_llm_and_rules(
    llm: Optional[PatientResponseModel], rules: PatientResponseModel, message: str
) -> PatientResponseModel:
    """Решение модели + разбор по правилам. Числа здоровья берем только те, что есть в тексте сообщения."""
    if llm is None:
        return rules
    rules_has_data = has_report_data(rules.model_dump())
    if llm.intent in ("request_slots", "show_plan", "ask_advice"):
        # Если в тексте есть показатели, их сохранение важнее любого другого решения модели
        return rules if rules_has_data else llm

    out = rules.model_copy()
    digits = digits_in(message)
    if out.systolic is None and llm.systolic is not None and llm.diastolic is not None:
        if str(llm.systolic) in digits and str(llm.diastolic) in digits:
            out.systolic, out.diastolic = llm.systolic, llm.diastolic
    if out.pulse is None and llm.pulse is not None and str(llm.pulse) in digits:
        out.pulse = llm.pulse
    if out.medication_taken is None and llm.medication_taken is not None:
        out.medication_taken = llm.medication_taken
        out.skip_reason = llm.skip_reason
    if out.medication_taken is False and out.skip_reason is None:
        out.skip_reason = llm.skip_reason or "other"
    if out.raw_complaint is None and llm.raw_complaint:
        out.raw_complaint = llm.raw_complaint
    if out.raw_complaint:
        out.intent = "complain_side_effects"
    elif has_report_data(out.model_dump()):
        out.intent = "report_data"
    else:
        out.intent = rules.intent
    return sanitize_report(out)


def _last_user_text(state: dict[str, Any]) -> str:
    messages = state.get("messages") or []
    if not messages:
        return ""
    last = messages[-1]
    return str(getattr(last, "content", None) or (last.get("content") if isinstance(last, dict) else "") or "")


def has_report_data(parsed: Optional[dict[str, Any]]) -> bool:
    parsed = parsed or {}
    return any(parsed.get(k) is not None for k in ("systolic", "pulse", "medication_taken"))


def _times_word(n: Any) -> str:
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "несколько раз"
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} раз"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return f"{n} раза"
    return f"{n} раз"


def _format_slot_time(value: str) -> str:
    """ISO-время слота из бэкенда (UTC, суффикс Z) -> 'дд.мм чч:мм' в часовом поясе пациента."""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(ZoneInfo(settings.timezone)).strftime("%d.%m %H:%M")
    except Exception:
        return value


def _hhmm(value: Any) -> Optional[str]:
    return str(value)[:5] if value else None


async def _load_plan(state: dict[str, Any]):
    """Назначения врача: GET /patient/treatment-plan (tool). Возвращает (план, ошибка)."""
    plan = state.get("treatment_plan")
    if plan is not None:
        return plan, None
    try:
        return await backend_client.get_treatment_plan(state["patient_id"], state["jwt_token"]), None
    except Exception as exc:
        return None, str(exc)


def _plan_fields(plan: dict[str, Any]) -> tuple[str, str, str, str]:
    doctor = plan.get("doctor_name") or "врач"
    medication = plan.get("medication") or plan.get("prescribed_medication") or "назначенный препарат"
    frequency = _times_word(plan.get("frequency_per_day", plan.get("frequency", 2)))
    target = plan.get("target_bp") or f"{plan.get('target_systolic', 130)}/{plan.get('target_diastolic', 80)}"
    return doctor, medication, frequency, target


async def greeting_node(state: dict[str, Any]):
    plan, error = await _load_plan(state)
    if plan is None:
        return {
            "response_text": "Не удалось получить назначение из системы. Пожалуйста, попробуйте ещё раз.",
            "quick_replies": [],
            "error": error,
        }
    doctor, medication, frequency, target = _plan_fields(plan)
    text = (
        f"Здравствуйте! Врач {doctor} назначил вам {medication} с приемом {frequency} в день "
        f"(целевое давление {target}). Я буду помогать вам вести дневник наблюдений: "
        "пришлите давление, пульс или расскажите о самочувствии. "
        "Пожалуйста, укажите в настройках удобное время для утреннего и вечернего напоминания."
    )
    return {"treatment_plan": plan, "response_text": text, "quick_replies": [QUICK_REPLY_SETUP_TIME]}


async def plan_node(state: dict[str, Any]):
    """Сценарий 1: пациент просит показать план лечения."""
    plan, error = await _load_plan(state)
    if plan is None:
        return {
            "response_text": "Не удалось получить план лечения из системы. Пожалуйста, попробуйте ещё раз.",
            "quick_replies": [],
            "error": error,
        }
    doctor, medication, frequency, target = _plan_fields(plan)
    text = f"Ваш план лечения: врач {doctor} назначил {medication}, прием {frequency} в день, целевое давление {target}."
    morning, evening = _hhmm(plan.get("morning_time")), _hhmm(plan.get("evening_time"))
    if morning and evening:
        text += f" Время приема: утром в {morning}, вечером в {evening}."
    text += " Пришлите давление и пульс, например «120/80, 70», и я внесу их в дневник."
    return {"treatment_plan": plan, "response_text": text, "quick_replies": [QUICK_REPLY_ADD_BP]}


async def nlu_node(state: dict[str, Any]):
    message = _last_user_text(state)
    rules = _fallback_parse(message)
    parsed = rules
    if llm_enabled():
        try:
            llm_result = await llm_parse_message(message, TOOL_PROMPT)
            parsed = _merge_llm_and_rules(llm_result, rules, message)
        except Exception as exc:  # LLM недоступен: остаемся на разборе по правилам
            logger.warning("LLM недоступен, использую разбор по правилам: %s", exc)
            parsed = rules
    return {"parsed_report": parsed.model_dump()}


async def rag_advice_node(state: dict[str, Any]):
    docs = retriever.search(_last_user_text(state))
    if docs:
        answer = (
            "По утвержденным материалам CardioFlow:\n\n" + "\n\n".join(docs[:2]) +
            "\n\nЭто общая информация, индивидуальные рекомендации даёт ваш врач."
        )
    else:
        answer = (
            "Я могу помочь зафиксировать ваши показатели и передать вопрос врачу. "
            "Индивидуальные медицинские рекомендации без подтвержденных материалов я не даю."
        )
    return {"response_text": answer, "quick_replies": []}


_GREETINGS = ("привет", "здравств", "добрый день", "доброе утро", "добрый вечер", "хай")


async def chat_node(state: dict[str, Any]):
    """Реплики без данных для отчета: приветствия, 'я в порядке', 'пока не принял' и т.п."""
    low = _last_user_text(state).lower()
    quick: list[str] = []
    if "настрой" in low and ("время" in low or "напомин" in low):
        text = "Время утреннего и вечернего приема можно задать на странице «Лечение» в разделе «Расписание приема»."
    elif any(x in low for x in _PENDING):
        text = "Хорошо. Не забудьте принять препарат по назначению врача, а потом напишите мне, как самочувствие."
    elif any(low.startswith(x) or f" {x}" in low for x in _GREETINGS):
        text = (
            "Здравствуйте! Я ассистент CardioFlow: помогаю вести дневник давления и приема лекарств. "
            "Могу показать план лечения, записать ваши показатели или ответить на вопросы по питанию и образу жизни."
        )
        quick = [QUICK_REPLY_SHOW_PLAN, QUICK_REPLY_ADD_BP]
    else:
        text = (
            "Я здесь, чтобы помочь вести дневник. Напишите давление (например, 130/85), пульс, "
            "принимали ли вы лекарство и как себя чувствуете."
        )
    return {"response_text": text, "quick_replies": quick}


async def backend_report_node(state: dict[str, Any]):
    parsed = state.get("parsed_report") or {}
    report = {
        key: parsed.get(key)
        for key in ("systolic", "diastolic", "pulse", "medication_taken", "skip_reason", "raw_complaint")
    }
    report["patient_id"] = state["patient_id"]

    # Предыдущий замер нужен, чтобы заметить улучшение (сценарий 2); без него отчет все равно сохраняем
    previous = None
    if parsed.get("systolic") is not None:
        try:
            previous = await backend_client.get_latest_measurement(state["jwt_token"])
        except Exception as exc:
            logger.warning("Не удалось получить предыдущий замер: %s", exc)
    try:
        result = await backend_client.submit_patient_report(report, state["jwt_token"])
    except Exception as exc:
        return {
            "response_text": "Не удалось сохранить данные в CardioFlow. Пожалуйста, повторите отправку.",
            "quick_replies": [],
            "error": str(exc),
        }
    return {
        "risk_level": result.get("risk_level"),
        "action_required": result.get("action_required"),
        "backend_result": result,
        "previous_measurement": previous,
    }


def _status_sentence(risk: Optional[str]) -> str:
    return f"Статус: {STATUS_TEXT[risk]}." if risk in STATUS_TEXT else ""


async def clarify_symptoms_node(state: dict[str, Any]):
    parsed = state.get("parsed_report") or {}
    action = state.get("action_required")
    risk = state.get("risk_level")
    parts = []
    if parsed.get("systolic") is not None:
        parts.append(f"Я записал давление {parsed['systolic']}/{parsed['diastolic']}.")
        status = _status_sentence(risk)
        if status:
            parts.append(status)
    if parsed.get("medication_taken") is False and parsed.get("skip_reason") == "side_effects":
        parts.append(SKIP_CONFIRMATION)

    if action == "book_appointment":
        parts.append("Пожалуйста, присядьте и спокойно отдохните. Как давно появились симптомы и сохраняются ли они сейчас?")
    elif risk == "warning" or action == "repeat_measurement":
        parts.append(
            f"Показатель выше целевого. Пожалуйста, отдохните: посидите спокойно и перемерьте давление через "
            f"{REMEASURE_MINUTES} минут, а затем пришлите мне новый результат. Если станет хуже, сразу напишите."
        )
    elif parsed.get("raw_complaint"):
        parts.append("Спасибо, я зафиксировал ваше самочувствие. Как давно появились эти симптомы и сохраняются ли они сейчас?")
    else:
        parts.append(
            "Пожалуйста, присядьте и спокойно отдохните. Уточните, как вы себя сейчас чувствуете: "
            "есть ли головная боль, тошнота или головокружение?"
        )
    return {"response_text": " ".join(parts), "quick_replies": []}


async def slots_proposal_node(state: dict[str, Any]):
    """GET /slots/available (tool). При критическом замере окно записи уже открыл backend (show_appointment_slots)."""
    base = state.get("response_text") or ""
    # Пациент сам попросил запись: backend ничего не слал, поэтому просим интерфейс открыть окно записи
    requested_by_patient = not (state.get("backend_result") or {}).get("action_required") == "book_appointment"
    events = [{"event": "show_appointment_slots", "data": {"reason": "patient_request"}}] if requested_by_patient else []
    try:
        slots = await backend_client.search_available_slots(state["jwt_token"], limit=3)
    except Exception as exc:
        text = (base + "\n\n" if base else "") + "Сейчас не удалось получить свободные окна врача. Пожалуйста, попробуйте позже."
        return {"available_slots": [], "response_text": text, "quick_replies": [], "events": [], "error": str(exc)}
    if not slots:
        extra = "Сейчас свободных окон к врачу не найдено. Я сохранил данные, и вы можете повторить поиск позже."
        events = []
    else:
        formatted = "\n".join(f"• {s.get('doctor_name', 'Врач')} — {_format_slot_time(s.get('datetime', ''))}" for s in slots)
        extra = "Ближайшие окна для записи (также откроется окно записи, выберите удобное время):\n" + formatted
    return {
        "available_slots": slots,
        "response_text": (base + "\n\n" if base else "") + extra,
        "quick_replies": [],
        "events": events,
        "action_required": "book_appointment" if slots else state.get("action_required"),
    }


def _improvement_text(state: dict[str, Any]) -> str:
    """Сценарий 2: было warning/critical, стало stable - хвалим за контроль."""
    prev = state.get("previous_measurement") or {}
    parsed = state.get("parsed_report") or {}
    if (
        state.get("risk_level") == "stable"
        and prev.get("risk_status") in ("warning", "critical")
        and prev.get("systolic") is not None
        and parsed.get("systolic") is not None
    ):
        return (
            f" Состояние улучшилось: было {prev['systolic']}/{prev['diastolic']}, "
            f"стало {parsed['systolic']}/{parsed['diastolic']}. "
            "Вы молодец: вовремя отдохнули и перемерили давление. Такой контроль очень помогает вашему врачу."
        )
    return ""


async def confirmation_node(state: dict[str, Any]):
    parsed = state.get("parsed_report") or {}
    saved = []
    if parsed.get("systolic") is not None:
        saved.append(f"давление {parsed['systolic']}/{parsed['diastolic']}")
    if parsed.get("pulse") is not None:
        saved.append(f"пульс {parsed['pulse']}")
    if parsed.get("medication_taken") is True:
        saved.append("прием лекарства отмечен")
    elif parsed.get("medication_taken") is False:
        saved.append("пропуск приема отмечен")
    text = "Спасибо, зафиксировал: " + ", ".join(saved) + "." if saved else "Спасибо, зафиксировал ваши данные."
    status = _status_sentence(state.get("risk_level"))
    if status:
        text += " " + status
    improvement = _improvement_text(state)
    if improvement:
        text += improvement
    elif state.get("risk_level") == "stable":
        text += " Так держать! Продолжайте измерять давление в привычное время."
    return {"response_text": text, "quick_replies": []}


async def appointment_booked_node(state: dict[str, Any]):
    """Сценарий 3: пациент выбрал слот и записан. Backend присылает {"doctor_name", "datetime"} в тексте события."""
    raw = _last_user_text(state)
    try:
        info = json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        info = {}
    doctor = info.get("doctor_name") if isinstance(info, dict) else None
    when = _format_slot_time(info.get("datetime", "")) if isinstance(info, dict) and info.get("datetime") else ""
    head = "Вы успешно записаны на приём"
    if doctor:
        head += f" к врачу {doctor}"
    if when:
        head += f" на {when}"
    head += "."
    return {"response_text": f"{head} {HYPERTENSIVE_CRISIS_RULES}", "quick_replies": []}
