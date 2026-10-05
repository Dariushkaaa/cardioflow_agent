from typing import Annotated, Any, Dict, List, Optional

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    patient_id: str
    jwt_token: str
    messages: Annotated[List[Any], add_messages]
    treatment_plan: Optional[Dict[str, Any]]
    parsed_report: Optional[Dict[str, Any]]
    risk_level: Optional[str]
    action_required: Optional[str]
    available_slots: Optional[List[Dict[str, Any]]]
    backend_result: Optional[Dict[str, Any]]
    previous_measurement: Optional[Dict[str, Any]]
    events: List[Dict[str, Any]]
    response_text: str
    quick_replies: List[str]
    event_type: str
    error: Optional[str]
