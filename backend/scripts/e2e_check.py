"""Сквозная проверка связки frontend-протокола -> backend -> agent -> backend -> WebSocket.

Запуск (из корня репозитория, когда система поднята через docker compose):

    docker compose exec backend python scripts/e2e_check.py

Скрипт повторяет то, что делает фронтенд: получает JWT, открывает WebSocket, просит приветствие,
отправляет реплики пациента и проверяет, что агент вызвал backend (Tool Calling), риск посчитан
детерминированным движком, а события интерфейса дошли до сокета. Рассчитан на режим агента без LLM
(LLM_API_KEY пуст): с LLM формулировки и разбор реплик могут отличаться.
"""
import asyncio
import json
import sys
from urllib.parse import urlparse

import httpx
import websockets

from app.core.config import settings

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
PATIENT_ID = "d3b07384-d113-4ec6-a563-9a3d46532401"


def check(name: str, ok: bool, details: str = "") -> None:
    print(f"[{'OK' if ok else 'FAIL'}] {name} {details}")
    if not ok:
        raise SystemExit(1)


async def collect_until_agent_message(ws, timeout: float = 25.0) -> list[dict]:
    """Читает события сокета до сообщения агента (оно приходит последним в цепочке)."""
    events: list[dict] = []
    while True:
        event = json.loads(await asyncio.wait_for(ws.recv(), timeout))
        events.append(event)
        if event["event"] == "agent_message":
            return events


async def main() -> None:
    agent_url = urlparse(settings.AGENT_SERVICE_URL)
    agent_health = f"{agent_url.scheme}://{agent_url.netloc}/health"

    async with httpx.AsyncClient(base_url=BASE, timeout=15) as client:
        r = await client.get("/health")
        check("backend /health", r.status_code == 200)
        r = await client.get(agent_health)
        check("agent /health", r.status_code == 200, agent_health)

        r = await client.post("/api/v1/auth/token", json={"patient_id": PATIENT_ID})
        check("JWT выдан", r.status_code == 200)
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        ws_url = f"{BASE.replace('http', 'ws', 1)}/ws/patient/{PATIENT_ID}?token={token}"
        async with websockets.connect(ws_url) as ws:
            # 1. Приветствие: backend -> agent (init_onboarding) -> backend (treatment-plan) -> WS
            await ws.send(json.dumps({"action": "init_onboarding", "data": {}}))
            events = await collect_until_agent_message(ws)
            greeting = events[-1]["data"]["text"]
            check("приветствие агента с назначениями врача", "Периндоприл" in greeting, greeting[:90])

            # 2. Критический отчет с побочными эффектами
            await ws.send(
                json.dumps(
                    {
                        "action": "send_message",
                        "data": {"text": "Давление 170/105, пульс 90, таблетку не принял, тошнит"},
                    }
                )
            )
            events = await collect_until_agent_message(ws)
            names = [e["event"] for e in events]
            measurement = next((e["data"] for e in events if e["event"] == "new_measurement_status"), None)
            check(
                "WS: new_measurement_status (critical)",
                measurement is not None and measurement["risk_status"] == "critical",
                str(measurement),
            )
            check(
                "WS: new_measurement_status содержит id и timestamp для графика",
                bool(measurement and measurement.get("id") and measurement.get("timestamp")),
                str(measurement),
            )
            check("WS: show_appointment_slots", "show_appointment_slots" in names, str(names))
            reply = events[-1]["data"]["text"]
            check("агент предложил слоты и сослался на данные", "170/105" in reply and "•" in reply, reply[:120])

            # 3. Нормальный замер
            await ws.send(json.dumps({"action": "send_message", "data": {"text": "Давление 120/80, пульс 70"}}))
            events = await collect_until_agent_message(ws)
            measurement = next((e["data"] for e in events if e["event"] == "new_measurement_status"), None)
            check(
                "WS: new_measurement_status (stable)",
                measurement is not None and measurement["risk_status"] == "stable",
                str(measurement),
            )
            check("нет лишней эскалации на норме", "show_appointment_slots" not in [e["event"] for e in events])

            # 4. Вопрос по базе знаний (RAG)
            await ws.send(json.dumps({"action": "send_message", "data": {"text": "Сколько соли можно при гипертонии?"}}))
            events = await collect_until_agent_message(ws)
            reply = events[-1]["data"]["text"]
            check("RAG: ответ из базы знаний", "соль" in reply.lower(), reply[:100])

        # 5. Данные реально сохранены в БД
        r = await client.get("/api/v1/patient/measurements/latest", headers=headers)
        latest = r.json()
        check(
            "последний замер сохранен в БД",
            r.status_code == 200 and latest and latest["systolic"] == 120 and latest["risk_status"] == "stable",
            str(latest),
        )

        r = await client.get("/api/v1/patient/measurements", params={"limit": 30}, headers=headers)
        history = r.json() if r.status_code == 200 else []
        check(
            "история замеров для графика (GET /patient/measurements)",
            r.status_code == 200 and len(history) >= 2 and history[-1]["systolic"] == 120,
            str(history[-2:]),
        )

    print("\nСквозная проверка backend + agent пройдена.")


if __name__ == "__main__":
    asyncio.run(main())
