import asyncio
import contextlib
import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from backend.app.config import get_settings
from backend.app.core.events import get_event_bus
from backend.app.core.exceptions import AuthenticationError
from backend.app.core.logging import get_logger
from backend.app.core.security import decode_jwt_token

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


def authenticate_ws(
    websocket: WebSocket,
    token_param: str | None,
) -> dict[str, Any] | None:
    """
    Authenticate WebSocket client via cookie or query parameter token.
    Returns decoded token payload if valid, None if unauthenticated.
    """
    settings = get_settings()
    token = token_param or websocket.cookies.get("niko_access_token")
    if not token:
        return None

    try:
        payload = decode_jwt_token(
            token=token,
            secret_key=settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )
        return payload
    except AuthenticationError:
        return None


@router.websocket("/ws")
async def websocket_hub(
    websocket: WebSocket,
    token: str | None = Query(default=None),
) -> None:
    """
    Real-time bidirectional WebSocket Hub multiplexer.
    Streams pub/sub events (system metrics, chat chunks, approvals) from EventBus to client.
    Handles client heartbeat pings and topic subscriptions.
    """
    settings = get_settings()
    origin = websocket.headers.get("origin")

    # 1. Strict Origin Validation: prevent cross-site WebSocket hijacking (CSWSH)
    if not is_allowed_origin(origin, settings.WS_ALLOWED_ORIGINS):
        logger.warning("Rejected WebSocket connection with unauthorized origin", origin=origin)
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Forbidden: Origin not authorized to connect to local NIKO agent.",
        )
        return

    # 2. Authenticate client
    auth_payload = authenticate_ws(websocket, token)
    user_id = auth_payload.get("sub") if auth_payload else None

    await websocket.accept()
    logger.info("WebSocket connection established", user_id=user_id, origin=origin)

    # Subscribed topics for this connection (empty set means all topics)
    subscribed_topics: set[str] = set()
    event_bus = get_event_bus()

    async def event_forwarder() -> None:
        """Stream events from EventBus out to the WebSocket client."""
        with contextlib.suppress(asyncio.CancelledError):
            try:
                async for event in event_bus.subscribe():
                    # Filter by client subscription if client specified topic filters
                    if subscribed_topics and event.topic not in subscribed_topics:
                        continue

                    msg = {
                        "type": "event",
                        "topic": event.topic,
                        "event_type": event.event_type,
                        "payload": event.payload,
                        "timestamp": event.timestamp.isoformat(),
                    }
                    await websocket.send_text(json.dumps(msg))
            except Exception as exc:
                logger.debug("Event forwarder stopped", error=str(exc))

    forwarder_task = asyncio.create_task(event_forwarder())

    try:
        while True:
            raw_text = await websocket.receive_text()
            try:
                data = json.loads(raw_text)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON format"})
                continue

            msg_type = data.get("type")

            if msg_type == "ping":
                await websocket.send_json(
                    {
                        "type": "pong",
                        "timestamp": data.get("timestamp") or datetime.now(UTC).isoformat(),
                    }
                )

            elif msg_type == "auth":
                # Late authentication via WS message
                client_token = data.get("token")
                if client_token:
                    try:
                        auth_payload = decode_jwt_token(
                            token=client_token,
                            secret_key=settings.JWT_SECRET_KEY,
                            algorithm=settings.JWT_ALGORITHM,
                        )
                        user_id = auth_payload.get("sub")
                        await websocket.send_json({"type": "auth_ok", "user_id": user_id})
                    except AuthenticationError as err:
                        await websocket.send_json({"type": "auth_error", "message": str(err)})
                else:
                    await websocket.send_json({"type": "auth_error", "message": "Missing token"})

            elif msg_type == "subscribe":
                # Update topic filter
                topics = data.get("topics")
                if isinstance(topics, list):
                    subscribed_topics = {str(t) for t in topics}
                    await websocket.send_json(
                        {
                            "type": "subscribed",
                            "topics": list(subscribed_topics),
                        }
                    )
                else:
                    await websocket.send_json(
                        {"type": "error", "message": "'topics' must be a list of topic names"}
                    )

            else:
                await websocket.send_json(
                    {
                        "type": "ack",
                        "received": msg_type,
                    }
                )

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected", user_id=user_id)
    except Exception as exc:
        logger.warning("WebSocket exception terminated connection", error=str(exc))
    finally:
        forwarder_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await forwarder_task
