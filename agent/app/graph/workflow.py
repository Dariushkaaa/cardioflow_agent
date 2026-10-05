from langgraph.graph import END, START, StateGraph

from app.graph.nodes import (
    appointment_booked_node,
    backend_report_node,
    chat_node,
    clarify_symptoms_node,
    confirmation_node,
    greeting_node,
    has_report_data,
    nlu_node,
    plan_node,
    rag_advice_node,
    slots_proposal_node,
)
from app.graph.state import AgentState


def route_event(state):
    event = state.get("event_type")
    if event == "init_onboarding":
        return "greeting"
    if event == "appointment_booked":
        return "booked"
    return "nlu"


def route_intent(state):
    parsed = state.get("parsed_report") or {}
    intent = parsed.get("intent")
    if has_report_data(parsed):
        return "report"
    if intent == "ask_advice":
        return "rag"
    if intent == "request_slots":
        return "slots"
    if intent == "show_plan":
        return "plan"
    if parsed.get("intent") == "complain_side_effects":
        return "clarify"
    return "chat"


def route_after_report(state):
    if state.get("error"):
        return "end"
    if state.get("action_required") in ("book_appointment", "repeat_measurement"):
        return "clarify"
    if state.get("risk_level") in ("critical", "warning"):
        return "clarify"
    return "confirm"


def route_after_clarify(state):
    return "slots" if state.get("action_required") == "book_appointment" else "end"


def build_workflow():
    g = StateGraph(AgentState)
    g.add_node("greeting", greeting_node)
    g.add_node("booked", appointment_booked_node)
    g.add_node("plan", plan_node)
    g.add_node("nlu", nlu_node)
    g.add_node("rag", rag_advice_node)
    g.add_node("chat", chat_node)
    g.add_node("report", backend_report_node)
    g.add_node("clarify", clarify_symptoms_node)
    g.add_node("slots", slots_proposal_node)
    g.add_node("confirm", confirmation_node)

    g.add_conditional_edges(START, route_event, {"greeting": "greeting", "booked": "booked", "nlu": "nlu"})
    g.add_edge("greeting", END)
    g.add_edge("booked", END)
    g.add_edge("plan", END)
    g.add_conditional_edges(
        "nlu",
        route_intent,
        {"rag": "rag", "report": "report", "clarify": "clarify", "chat": "chat", "slots": "slots", "plan": "plan"},
    )
    g.add_edge("rag", END)
    g.add_edge("chat", END)
    g.add_conditional_edges("report", route_after_report, {"clarify": "clarify", "confirm": "confirm", "end": END})
    g.add_conditional_edges("clarify", route_after_clarify, {"slots": "slots", "end": END})
    g.add_edge("slots", END)
    g.add_edge("confirm", END)
    return g.compile()


workflow = build_workflow()
