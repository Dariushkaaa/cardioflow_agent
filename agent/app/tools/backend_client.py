from typing import Any, Optional

import httpx

from app.core.config import settings


class BackendClient:
    """Tool Calling: вызовы REST API бэкенда от имени пациента (JWT пациента пробрасывается как есть)."""

    def __init__(self, base_url: Optional[str] = None):
        self._base_url = base_url

    @property
    def base_url(self) -> str:
        return (self._base_url or settings.backend_api_url).rstrip("/")

    async def _request(self, method: str, path: str, token: str, **kwargs: Any) -> Any:
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            response = await client.request(method, f"{self.base_url}{path}", headers=headers, **kwargs)
            response.raise_for_status()
            return response.json()

    async def get_treatment_plan(self, patient_id: str, token: str) -> dict[str, Any]:
        # patient_id берется бэкендом из JWT (защита от IDOR), в запрос он не передается
        return await self._request("GET", "/patient/treatment-plan", token)

    async def get_latest_measurement(self, token: str) -> Optional[dict[str, Any]]:
        """Последний сохраненный замер (None, если замеров еще не было)."""
        data = await self._request("GET", "/patient/measurements/latest", token)
        return data if isinstance(data, dict) else None

    async def submit_patient_report(self, report_data: dict[str, Any], token: str) -> dict[str, Any]:
        return await self._request("POST", "/reports/", token, json=report_data)

    async def search_available_slots(self, token: str, limit: int = 3) -> list[dict[str, Any]]:
        data = await self._request(
            "GET", "/slots/available", token, params={"doctor_type": "therapist", "limit": limit}
        )
        return data.get("slots", [])


backend_client = BackendClient()
