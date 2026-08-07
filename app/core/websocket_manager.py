"""
Stage 7: Backend -> Frontend, real-time.

One WebSocket hub, shared across the whole app (created once in main.py's
lifespan and handed to endpoints via dependencies.py). Every stage
transition in the orchestrator calls `broadcast(...)` with one of the
event shapes from the schema doc:

    job_created | sandbox_started | sandbox_completed |
    ai_review_started | ai_review_completed | github_posted | job_failed

If nobody's connected, broadcast is a no-op — the pipeline never blocks
on the dashboard being open.
"""
import json
from typing import Any

from fastapi import WebSocket

from app.core.logging import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)
        logger.info(f"WebSocket connected ({len(self._connections)} total)")

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)
        logger.info(f"WebSocket disconnected ({len(self._connections)} total)")

    async def broadcast(self, event: dict[str, Any]) -> None:
        if not self._connections:
            return
        payload = json.dumps(event, default=str)
        dead: set[WebSocket] = set()
        for ws in self._connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self._connections.discard(ws)


# Single shared instance. Simple, explicit, and fine for a hackathon-scale
# single-process deployment. If you ever run multiple backend workers,
# swap this for a Redis pub/sub channel instead.
manager = ConnectionManager()
