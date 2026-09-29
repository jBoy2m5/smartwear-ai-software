"""Validated live telemetry WebSocket endpoint."""

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from backend.core.config import Settings
from backend.mock.telemetry import TelemetrySimulator
from backend.schemas import TelemetryUpdate
from backend.websocket.manager import ConnectionManager


logger = logging.getLogger(__name__)
router = APIRouter(tags=["Live telemetry"])


@router.websocket("/ws/live-stream")
async def live_stream(
    websocket: WebSocket,
    simulate: bool = False,
    api_key: str | None = None,
) -> None:
    """Broadcast validated telemetry or stream backend mock telemetry."""
    settings: Settings = websocket.app.state.settings
    manager: ConnectionManager = websocket.app.state.connection_manager
    if settings.api_key and api_key != settings.api_key:
        await websocket.close(code=1008, reason="Invalid or missing API key")
        return

    await manager.connect(websocket)
    try:
        if simulate:
            async for message in TelemetrySimulator().stream():
                await manager.send(websocket, message.model_dump(mode="json"))
        else:
            await _receive_and_broadcast(websocket, manager)
    except WebSocketDisconnect:
        logger.debug("WebSocket client disconnected")
    except RuntimeError:
        logger.debug("WebSocket transport closed")
    finally:
        await manager.disconnect(websocket)


async def _receive_and_broadcast(
    websocket: WebSocket,
    manager: ConnectionManager,
) -> None:
    """Validate inbound messages before broadcasting them."""
    while True:
        payload = await websocket.receive_json()
        try:
            message = TelemetryUpdate.model_validate(payload)
        except ValidationError as exc:
            await manager.send(
                websocket,
                {
                    "event": "VALIDATION_ERROR",
                    "detail": exc.errors(include_url=False, include_context=False),
                },
            )
            continue
        await manager.broadcast(message.model_dump(mode="json"))

