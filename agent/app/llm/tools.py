"""Описание функций (Tool Calling), которые модель может вызвать, и разбор ее решения.

Модель только выбирает функцию и заполняет аргументы. Сами вызовы REST API бэкенда
(/reports/, /slots/available, /patient/treatment-plan) выполняют узлы графа через backend_client,
а клинический риск считает только детерминированный движок бэкенда.
"""
import re
from typing import Any, Optional

from app.llm.client import LLMReply, llm_client
from app.schemas.patient_report import PatientResponseModel

TOOL_SUBMIT_REPORT = "submit_patient_report"
TOOL_GET_SLOTS = "get_available_slots"
TOOL_GET_PLAN = "get_treatment_plan"
TOOL_SEARCH_KB = "search_knowledge_base"

TOOLS: list[dict[str, Any]] = [
    {
        "name": TOOL_SUBMIT_REPORT,
        "description": (
            "Сохранить данные пациента из его сообщения: давление, пульс, принял ли он лекарство, жалобы. "
            "Вызывай, если в сообщении есть цифры давления/пульса, речь о приеме или пропуске таблетки или о самочувствии."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "systolic": {"type": "integer", "description": "Верхнее (систолическое) давление, например 120"},
                "diastolic": {"type": "integer", "description": "Нижнее (диастолическое) давление, например 80"},
                "pulse": {"type": "integer", "description": "Пульс, уд/мин"},
                "medication_taken": {
                    "type": "boolean",
                    "description": "true - принял лекарство, false - пропустил; не указывай, если о лекарстве не говорилось",
                },
                "skip_reason": {
                    "type": "string",
                    "enum": ["forgot", "side_effects", "late", "other"],
                    "description": "Причина пропуска, только если лекарство пропущено",
                },
                "raw_complaint": {"type": "string", "description": "Жалобы на самочувствие дословно (тошнота, головокружение и т.п.)"},
            },
            "required": [],
        },
    },
    {
        "name": TOOL_GET_SLOTS,
        "description": "Получить ближайшие свободные окна для записи к врачу. Вызывай, когда пациент просит записать его к врачу.",
        "parameters": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "Сколько окон показать, по умолчанию 3"}},
            "required": [],
        },
    },
    {
        "name": TOOL_GET_PLAN,
        "description": "Получить назначения врача: препарат, кратность приема, целевое давление. Вызывай, когда пациент спрашивает про свое лечение.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": TOOL_SEARCH_KB,
        "description": "Найти ответ в утвержденных материалах CardioFlow: питание, соль, спорт, сон, правила измерения давления.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Вопрос пациента"}},
            "required": ["query"],
        },
    },
]


def _to_int(value: Any) -> Optional[int]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(float(str(value).replace(",", ".").strip()))
    except (TypeError, ValueError):
        return None


def _to_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        low = value.strip().lower()
        if low in ("true", "yes", "да", "1"):
            return True
        if low in ("false", "no", "нет", "0"):
            return False
    return None


def tool_call_to_report(name: str, args: dict[str, Any]) -> Optional[PatientResponseModel]:
    """Решение модели -> PatientResponseModel (тот же формат, что и у разбора по правилам)."""
    if name == TOOL_GET_SLOTS:
        return PatientResponseModel(intent="request_slots")
    if name == TOOL_GET_PLAN:
        return PatientResponseModel(intent="show_plan")
    if name == TOOL_SEARCH_KB:
        return PatientResponseModel(intent="ask_advice")
    if name == TOOL_SUBMIT_REPORT:
        complaint = args.get("raw_complaint")
        taken = _to_bool(args.get("medication_taken"))
        reason = args.get("skip_reason") if isinstance(args.get("skip_reason"), str) else None
        report = PatientResponseModel(
            systolic=_to_int(args.get("systolic")),
            diastolic=_to_int(args.get("diastolic")),
            pulse=_to_int(args.get("pulse")),
            medication_taken=taken,
            skip_reason=reason if taken is False else None,
            raw_complaint=str(complaint).strip() if complaint else None,
        )
        report.intent = "complain_side_effects" if report.raw_complaint else "report_data"
        return report
    return None


async def llm_parse_message(message: str, system_prompt: str) -> Optional[PatientResponseModel]:
    """Спрашивает модель, какую функцию вызвать для реплики. None - модель ответила без вызова функции."""
    reply: LLMReply = await llm_client.chat(
        [{"role": "system", "content": system_prompt}, {"role": "user", "content": message}],
        functions=TOOLS,
        temperature=0.0,
    )
    if not reply.function_name:
        return None
    return tool_call_to_report(reply.function_name, reply.function_args)


def digits_in(text: str) -> set[str]:
    return set(re.findall(r"\d+", text))
