import asyncio
import logging
from collections import defaultdict
from typing import Any, Coroutine

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Менеджер активных WebSocket-подключений (в памяти процесса)."""

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._tasks: set[asyncio.Task] = set()

    def register(self, patient_id: str, websocket: WebSocket) -> None:
        self._connections[patient_id].add(websocket)

    def disconnect(self, patient_id: str, websocket: WebSocket) -> None:
        sockets = self._connections.get(patient_id)
        if sockets is None:
            return
        sockets.discard(websocket)
        if not sockets:
            self._connections.pop(patient_id, None)

    def is_connected(self, patient_id: str) -> bool:
        return bool(self._connections.get(patient_id))

    async def send_event(self, patient_id: str, event: str, data: dict[str, Any]) -> bool:
        """Отправляет событие всем подключениям пациента. True, если доставлено хотя бы одному."""
        patient_id = str(patient_id)
        delivered = False
        for websocket in list(self._connections.get(patient_id, ())):
            try:
                await websocket.send_json({"event": event, "data": data})
                delivered = True
            except Exception:  # соединение разорвано
                self.disconnect(patient_id, websocket)
        return delivered

    def spawn(self, coro: Coroutine[Any, Any, Any]) -> None:
        """Запускает фоновую задачу и хранит ссылку на нее, чтобы ее не собрал GC."""
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)


manager = ConnectionManager()
