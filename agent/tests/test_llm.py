"""Разбор ответов GigaChat / OpenAI и решение модели о вызове функции (без сети)."""
import asyncio
from unittest import mock

from app.core.config import settings
from app.graph.nodes import _fallback_parse, _merge_llm_and_rules
from app.llm.client import LLMClient, parse_json_object, parse_reply
from app.llm.tools import TOOL_GET_SLOTS, TOOL_SUBMIT_REPORT, tool_call_to_report


def test_parse_gigachat_function_call_with_dict_arguments():
    reply = parse_reply(
        {
            "choices": [
                {
                    "finish_reason": "function_call",
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "function_call": {"name": "submit_patient_report", "arguments": {"systolic": 170, "diastolic": 105}},
                    },
                }
            ]
        }
    )
    assert reply.function_name == "submit_patient_report"
    assert reply.function_args == {"systolic": 170, "diastolic": 105}


def test_parse_openai_tool_calls_with_json_string():
    reply = parse_reply(
        {"choices": [{"message": {"content": None, "tool_calls": [{"function": {"name": "get_available_slots", "arguments": '{"limit": 3}'}}]}}]}
    )
    assert reply.function_name == "get_available_slots" and reply.function_args == {"limit": 3}


def test_parse_function_call_written_as_text():
    reply = parse_reply(
        {"choices": [{"message": {"content": '```json\n{"name": "get_treatment_plan", "arguments": {}}\n```'}}]}
    )
    assert reply.function_name == "get_treatment_plan"


def test_parse_json_object_variants():
    assert parse_json_object('{"a": 1}') == {"a": 1}
    assert parse_json_object('Вот: {"a": 1} спасибо') == {"a": 1}
    assert parse_json_object("не json") == {}
    assert parse_json_object({"a": 2}) == {"a": 2}


def test_tool_call_to_report():
    report = tool_call_to_report(
        TOOL_SUBMIT_REPORT,
        {"systolic": "150", "diastolic": 95, "medication_taken": "false", "skip_reason": "forgot"},
    )
    assert (report.systolic, report.diastolic, report.medication_taken, report.skip_reason) == (150, 95, False, "forgot")
    assert tool_call_to_report(TOOL_GET_SLOTS, {}).intent == "request_slots"


def test_llm_numbers_must_appear_in_message():
    message = "у меня давление сто пятьдесят на девяносто пять"
    llm = tool_call_to_report(TOOL_SUBMIT_REPORT, {"systolic": 150, "diastolic": 95})
    merged = _merge_llm_and_rules(llm, _fallback_parse(message), message)
    assert merged.systolic is None  # модель не может подставить числа, которых нет в тексте

    message = "давление 150 на 95"
    merged = _merge_llm_and_rules(llm, _fallback_parse(message), message)
    assert (merged.systolic, merged.diastolic) == (150, 95)


def test_gigachat_detection_and_auth_key():
    client = LLMClient()
    with mock.patch.object(settings, "llm_provider", "auto"), mock.patch.object(settings, "llm_base_url", "https://api.giga.chat/v1"):
        assert client.is_gigachat
    with mock.patch.object(settings, "llm_provider", "auto"), mock.patch.object(settings, "llm_base_url", "https://openrouter.ai/api/v1"), \
         mock.patch.object(settings, "llm_model_name", "meta-llama/x"):
        assert not client.is_gigachat
    with mock.patch.object(settings, "llm_api_key", "client:secret"):
        assert client._authorization_key() == "Y2xpZW50OnNlY3JldA=="
    with mock.patch.object(settings, "llm_api_key", "Basic QUJD"):
        assert client._authorization_key() == "QUJD"


def test_bearer_key_skips_oauth():
    client = LLMClient()
    with mock.patch.object(settings, "llm_api_key", "Bearer abc"):
        assert asyncio.run(client._access_token()) == "abc"
