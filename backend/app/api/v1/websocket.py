from fastapi import APIRouter, WebSocket, status

from backend.app.config import get_settings
from backend.app.core.logging import get_logger

logger = get_logger("websocket")
router = APIRouter(tags=["WebSocket Hub"])


def is_allowed_origin(origin: str | None, allowed_origins: list[str]) -> bool:
    """Validate whether the Origin header matches allowed localhost frontend origins."""
    if not origin:
        # Allow native non-browser clients (CLI tools, desktop scripts) where Origin header is absent
        return True

    # Strip trailing slashes for clean comparison
    normalized_origin = origin.rstrip("/")
    normalized_allowed = [o.rstrip("/") for o in allowed_origins]

    return normalized_origin in normalized_allowed


@router.websocket("/ws")
async def websocket_hub(websocket: WebSocket) -> None:
    settings = get_settings()
    origin = websocket.headers.get("origin")

    # Strict Origin Validation to block cross-site WebSocket hijacking from foreign websites
    if not is_allowed_origin(origin, settings.WS_ALLOWED_ORIGINS):
        logger.warning("Rejected WebSocket connection with unauthorized origin", origin=origin)
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Forbidden: Origin not authorized to connect to local NIKO agent.",
        )
        return

    await websocket.accept()
    logger.info("WebSocket connection established", origin=origin)

    try:
        while True:
            data = await websocket.receive_json()
            # Simple ping/pong echo for connectivity verification
            msg_type = data.get("type")
            if msg_type == "ping":
                await websocket.send_json({"type": "pong", "timestamp": data.get("timestamp")})
            else:
                await websocket.send_json(
                    {
                        "type": "ack",
                        "received": msg_type,
                        "status": "ready",
                    }
                )
    except Exception:
        logger.info("WebSocket client disconnected")
