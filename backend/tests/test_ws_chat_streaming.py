import asyncio
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.app.config import get_settings
from backend.app.core.security import create_jwt_token
from backend.app.llm.exceptions import AllProvidersExhaustedError
from backend.app.llm.types import NormalizedToolCall, StreamChunk
from backend.app.main import create_app


def test_ws_chat_streaming_chunks() -> None:
    """Verify chat streaming delivers chat:chunk and chat:done events over the WS hub."""
    app = create_app()
    client = TestClient(app)
    settings = get_settings()

    valid_token = create_jwt_token(
        payload={"sub": "user_ws_test", "username": "ws_owner", "role": "owner"},
        secret_key=settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
        expires_delta=timedelta(minutes=15),
    )

    async def mock_stream_chunks(*_args: Any, **_kwargs: Any) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(content="Hello ")
        yield StreamChunk(content="from ")
        yield StreamChunk(content="NIKO!")

    with (
        patch("backend.app.llm.orchestrator.LLMOrchestrator.chat_stream", side_effect=mock_stream_chunks),
        client.websocket_connect(
            f"/ws?token={valid_token}", headers={"origin": "http://localhost:5173"}
        ) as ws,
    ):
        ws.send_json({
            "type": "chat",
            "request_id": "req-stream-1",
            "content": "Say hello",
        })

        received_chunks = []
        done_received = False

        # Collect streaming messages
        for _ in range(10):
            msg = ws.receive_json()
            if msg.get("type") == "chat:error":
                pytest.fail(f"Received unexpected chat error: {msg}")
            if msg.get("type") == "chat:chunk":
                received_chunks.append(msg.get("chunk"))
            elif msg.get("type") == "chat:done":
                done_received = True
                break

        assert "".join(received_chunks) == "Hello from NIKO!"
        assert done_received is True


def test_ws_chat_streaming_tool_call() -> None:
    """Verify chat streaming emits chat:tool_call when an LLM invokes a skill."""
    app = create_app()
    client = TestClient(app)
    settings = get_settings()

    valid_token = create_jwt_token(
        payload={"sub": "user_ws_tool", "username": "ws_tool_owner", "role": "owner"},
        secret_key=settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
        expires_delta=timedelta(minutes=15),
    )

    call_count = 0

    async def mock_stream_with_tool(*_args: Any, **_kwargs: Any) -> AsyncIterator[StreamChunk]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield StreamChunk(
                tool_calls=[
                    NormalizedToolCall(
                        id="tc_123",
                        name="datetime",
                        arguments={},
                    )
                ]
            )
        else:
            yield StreamChunk(content="The current time was fetched.")

    with (
        patch("backend.app.llm.orchestrator.LLMOrchestrator.chat_stream", side_effect=mock_stream_with_tool),
        client.websocket_connect(
            f"/ws?token={valid_token}", headers={"origin": "http://localhost:5173"}
        ) as ws,
    ):
        ws.send_json({
            "type": "chat",
            "request_id": "req-tool-1",
            "content": "What time is it?",
        })

        tool_call_received = False
        done_received = False

        for _ in range(10):
            msg = ws.receive_json()
            if msg.get("type") == "chat:error":
                pytest.fail(f"Received unexpected chat error: {msg}")
            if msg.get("type") == "chat:tool_call":
                assert msg.get("name") == "datetime"
                tool_call_received = True
            elif msg.get("type") == "chat:done":
                done_received = True
                break

        assert tool_call_received is True
        assert done_received is True


def test_ws_chat_cancellation() -> None:
    """Verify chat streaming can be cancelled on demand via chat:cancel."""
    app = create_app()
    client = TestClient(app)
    settings = get_settings()

    valid_token = create_jwt_token(
        payload={"sub": "user_ws_cancel", "username": "ws_cancel_owner", "role": "owner"},
        secret_key=settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
        expires_delta=timedelta(minutes=15),
    )

    async def mock_slow_stream(*_args: Any, **_kwargs: Any) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(content="Starting...")
        await asyncio.sleep(0.3)
        yield StreamChunk(content="Never reached")

    with (
        patch("backend.app.llm.orchestrator.LLMOrchestrator.chat_stream", side_effect=mock_slow_stream),
        client.websocket_connect(
            f"/ws?token={valid_token}", headers={"origin": "http://localhost:5173"}
        ) as ws,
    ):
        ws.send_json({
            "type": "chat",
            "request_id": "req-cancel-1",
            "content": "Take a long time",
        })

        first_msg = ws.receive_json()
        assert first_msg.get("type") == "chat:chunk"
        assert first_msg.get("chunk") == "Starting..."

        # Send cancel request
        ws.send_json({
            "type": "chat:cancel",
            "request_id": "req-cancel-1",
        })

        # Expect cancel_ack and/or cancelled
        received_types = []
        for _ in range(5):
            msg = ws.receive_json()
            received_types.append(msg.get("type"))
            if "chat:cancelled" in received_types or "chat:cancel_ack" in received_types:
                break

        assert "chat:cancel_ack" in received_types or "chat:cancelled" in received_types


def test_ws_chat_cooldown_banner_on_exhaustion() -> None:
    """Verify chat streaming emits chat:cooldown_banner when all providers are exhausted."""
    app = create_app()
    client = TestClient(app)
    settings = get_settings()

    valid_token = create_jwt_token(
        payload={"sub": "user_ws_exhaust", "username": "ws_exhaust_owner", "role": "owner"},
        secret_key=settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
        expires_delta=timedelta(minutes=15),
    )

    async def mock_exhausted_stream(*_args: Any, **_kwargs: Any) -> AsyncIterator[StreamChunk]:
        if False:
            yield StreamChunk()
        raise AllProvidersExhaustedError(
            role="chat",
            attempts=[{"target": "gemini/gemini-2.0-flash", "status": "cooldown: predictive"}],
        )

    with (
        patch("backend.app.llm.orchestrator.LLMOrchestrator.chat_stream", side_effect=mock_exhausted_stream),
        client.websocket_connect(
            f"/ws?token={valid_token}", headers={"origin": "http://localhost:5173"}
        ) as ws,
    ):
        ws.send_json({
            "type": "chat",
            "request_id": "req-exhaust-1",
            "content": "Perform exhausted request",
        })

        msg = ws.receive_json()
        assert msg.get("type") == "chat:cooldown_banner"
        assert "all providers cooling down, shortest reset in" in msg.get("message", "")
        assert msg.get("role") == "chat"
        assert msg.get("shortest_reset_seconds") is not None
