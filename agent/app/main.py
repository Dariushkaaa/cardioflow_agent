import logging
from typing import Optional

from fastapi import FastAPI, Header, HTTPException

from app.graph.workflow import workflow
from app.schemas.request import AgentProcessRequest, AgentProcessResponse

logger = logging.getLogger("cardioflow.agent")

app = FastAPI(title="CardioFlow Agent Service", version="1.0.0")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "cardioflow-agent"}


def _extract_token(request: AgentProcessRequest, authorization: Optional[str]) -> str:
    if request.jwt_token:
        return request.jwt_token
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    raise HTTPException(status_code=401, detail="JWT пациента не передан (jwt_token или заголовок Authorization)")


async def _run(request: AgentProcessRequest, authorization: Optional[str]) -> AgentProcessResponse:
    token = _extract_token(request, authorization)
    try:
        result = await workflow.ainvoke(
            {
                "patient_id": request.patient_id,
                "jwt_token": token,
                "messages": [{"role": "user", "content": request.message}],
                "event_type": request.event_type,
                "response_text": "",
                "quick_replies": [],
                "events": [],
            }
        )
    except Exception as exc:
        logger.exception("Agent workflow failed")
        raise HTTPException(status_code=502, detail=f"Agent workflow failed: {exc}") from exc
    reply = result.get("response_text", "") or ""
    return AgentProcessResponse(
        reply_text=reply,
        text=reply,
        quick_replies=result.get("quick_replies", []) or [],
        action_required=result.get("action_required"),
        events=result.get("events", []) or [],
    )


# Собственный путь агента (README, Swagger)
@app.post("/process", response_model=AgentProcessResponse)
async def process(request: AgentProcessRequest, authorization: Optional[str] = Header(default=None)):
    return await _run(request, authorization)


# Путь, который по умолчанию вызывает backend (AGENT_SERVICE_URL)
@app.post("/api/v1/agent/process", response_model=AgentProcessResponse)
async def process_v1(request: AgentProcessRequest, authorization: Optional[str] = Header(default=None)):
    return await _run(request, authorization)
