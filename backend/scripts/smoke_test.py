"""Smoke-тест запущенного сервера: python scripts/smoke_test.py [http://localhost:8000]

Проверяет выдачу токена, отчет агента, WebSocket-события, слоты, бронирование,
валидацию расписания и защиту от IDOR.
"""
import asyncio
import json
import sys
import uuid

import httpx

try:
    import websockets
except ImportError:  # websockets ставится вместе с uvicorn[standard]
    websockets = None

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
PATIENT_ID = "d3b07384-d113-4ec6-a563-9a3d46532401"


def check(name: str, ok: bool, details: str = "") -> None:
    print(f"[{'OK' if ok else 'FAIL'}] {name} {details}")
    if not ok:
        raise SystemExit(1)


async def collect_ws_events(ws, expected: int, timeout: float = 5.0) -> list[dict]:
    events = []
    try:
        while len(events) < expected:
            events.append(json.loads(await asyncio.wait_for(ws.recv(), timeout)))
    except asyncio.TimeoutError:
        pass
    return events


async def main() -> None:
    async with httpx.AsyncClient(base_url=BASE, timeout=10) as client:
        r = await client.get("/health")
        check("health", r.status_code == 200)

        r = await client.post("/api/v1/auth/token", json={"patient_id": PATIENT_ID})
        check("dev token", r.status_code == 200, r.text[:80])
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        r = await client.get("/api/v1/patient/treatment-plan")
        check("treatment-plan без токена -> 401", r.status_code == 401)

        r = await client.get("/api/v1/patient/treatment-plan", headers=headers)
        check("treatment-plan", r.status_code == 200 and r.json()["patient_id"] == PATIENT_ID)

        ws = None
        if websockets is not None:
            ws = await websockets.connect(
                f"{BASE.replace('http', 'ws', 1)}/ws/patient/{PATIENT_ID}?token={token}"
            )

        report = {
            "patient_id": PATIENT_ID,
            "systolic": 165,
            "diastolic": 100,
            "pulse": 85,
            "medication_taken": False,
            "skip_reason": "side_effects",
            "raw_complaint": "тошнит от таблетки, кружится голова",
        }
        r = await client.post("/api/v1/reports/", json=report, headers=headers)
        body = r.json()
        check(
            "report 165/100 -> critical / book_appointment",
            r.status_code == 200 and body["risk_level"] == "critical" and body["action_required"] == "book_appointment",
            str(body),
        )

        if ws is not None:
            events = await collect_ws_events(ws, expected=2)
            names = [e["event"] for e in events]
            check(
                "WS: new_measurement_status + show_appointment_slots",
                "new_measurement_status" in names and "show_appointment_slots" in names,
                str(names),
            )
            await ws.close()

        r = await client.post(
            "/api/v1/reports/",
            json={"patient_id": PATIENT_ID, "medication_taken": True},
            headers=headers,
        )
        check("report без давления", r.status_code == 200 and r.json()["risk_level"] == "unknown", r.text)

        r = await client.post(
            "/api/v1/reports/", json={**report, "patient_id": str(uuid.uuid4())}, headers=headers
        )
        check("IDOR -> 403", r.status_code == 403)

        r = await client.get("/api/v1/slots/available", params={"doctor_type": "therapist", "limit": 3}, headers=headers)
        slots = r.json()["slots"]
        check("slots/available", r.status_code == 200 and len(slots) > 0, str(slots[:1]))

        r = await client.post(
            "/api/v1/appointments/book", json={"patient_id": PATIENT_ID, "slot_id": slots[0]["id"]}, headers=headers
        )
        check("book slot", r.status_code == 200 and r.json()["status"] == "booked", r.text)

        r = await client.post(
            "/api/v1/appointments/book", json={"patient_id": PATIENT_ID, "slot_id": slots[0]["id"]}, headers=headers
        )
        check("повторная бронь -> 409", r.status_code == 409)

        r = await client.post(
            "/api/v1/patient/schedule",
            json={"patient_id": PATIENT_ID, "morning_time": "09:00:00", "evening_time": "15:00:00"},
            headers=headers,
        )
        check("schedule 6ч -> 400", r.status_code == 400, r.text)

        r = await client.post(
            "/api/v1/patient/schedule",
            json={"patient_id": PATIENT_ID, "morning_time": "09:00:00", "evening_time": "21:00:00"},
            headers=headers,
        )
        check("schedule 12ч -> ok", r.status_code == 200 and r.json()["status"] == "validated_and_saved", r.text)

    print("\nВсе проверки пройдены.")


if __name__ == "__main__":
    asyncio.run(main())
