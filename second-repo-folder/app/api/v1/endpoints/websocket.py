from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.websocket_manager import manager

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Frontend connects here once and receives every job_created /
    sandbox_started / ... / job_failed event broadcast by the
    orchestrator, per Stage 7. No auth on this in dev — add a token
    query param check before a real deployment.
    """
    await manager.connect(websocket)
    try:
        while True:
            # We don't expect incoming messages, but need to await something
            # to detect disconnects.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
