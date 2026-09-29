import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.events import get_event_bus
from backend.app.db.models import User
from backend.app.llm.cooldown import cooldown_tracker
from backend.app.llm.deferred_queue import (
    DeferredChatRequest,
    DeferredQueue,
)
from backend.app.llm.types import ModelRole, ModelRolesConfig, RoleModelTarget


@pytest.fixture
def mock_roles_config() -> ModelRolesConfig:
    return ModelRolesConfig(
        light=[RoleModelTarget(provider="groq", model="test-light")],
        chat=[RoleModelTarget(provider="gemini", model="test-chat")],
        code=[],
        search=[],
    )


@pytest.mark.asyncio
async def test_deferred_queue_cooldown_banner_format(mock_roles_config: ModelRolesConfig) -> None:
    """Verify cooldown banner message format matches 'all providers cooling down, shortest reset in ...'"""
    queue = DeferredQueue(roles_config=mock_roles_config)
    bus = get_event_bus()

    received_events = []

    async def listener() -> None:
        async for ev in bus.subscribe(topic="chat:cooldown_banner"):
            received_events.append(ev)
            break

    task = asyncio.create_task(listener())
    await asyncio.sleep(0.01)

    # Force a cooldown on the model
    cooldown_tracker.record_429("gemini", "test-chat", retry_after_seconds=45)

    req = DeferredChatRequest(
        request_id="test_req_banner",
        user_id="u1",
        user_message="Hello while cooling",
        role=ModelRole.CHAT,
    )
    await queue.enqueue(req)

    await asyncio.wait_for(task, timeout=2.0)
    assert len(received_events) == 1
    ev = received_events[0]
    payload = ev.payload

    assert "all providers cooling down, shortest reset in" in payload["message"]
    assert payload["role"] == "chat"
    assert payload["shortest_reset_seconds"] > 0
    assert queue.active_banner is not None
    assert "all providers cooling down, shortest reset in" in queue.active_banner["message"]


@pytest.mark.asyncio
async def test_deferred_queue_cancellation(mock_roles_config: ModelRolesConfig) -> None:
    """Verify that a request in the deferred queue can be cancelled."""
    queue = DeferredQueue(roles_config=mock_roles_config)

    req = DeferredChatRequest(
        request_id="cancel_me_id",
        user_id="u1",
        user_message="Should be cancelled",
        role=ModelRole.CHAT,
    )
    await queue.enqueue(req)

    queued = await queue.list_queued()
    assert any(r.request_id == "cancel_me_id" for r in queued)

    cancelled = await queue.cancel("cancel_me_id")
    assert cancelled is True

    queued_after = await queue.list_queued()
    assert not any(r.request_id == "cancel_me_id" for r in queued_after)


@pytest.mark.asyncio
async def test_deferred_queue_auto_retry_execution(mock_roles_config: ModelRolesConfig, db_session: AsyncSession) -> None:
    """Verify that deferred queue worker automatically retries and executes requests when cooldown expires."""
    user = User(username="test_auto_retry_user", password_hash="disabled", role="owner")
    db_session.add(user)
    await db_session.flush()

    queue = DeferredQueue(roles_config=mock_roles_config, retry_interval_min=0.1)

    # Set a very short cooldown (0.2s)
    cooldown_tracker.record_429("gemini", "test-chat", retry_after_seconds=1)

    loop = asyncio.get_running_loop()
    future = loop.create_future()

    req = DeferredChatRequest(
        request_id="retry_auto_req",
        user_id=user.id,
        user_message="Hello auto retry",
        role=ModelRole.CHAT,
        future=future,
    )

    mock_chat_result = {
        "conversation_id": "conv-retried",
        "message_id": "msg-retried",
        "content": "Retried successfully after cooldown",
        "model_used": "gemini/test-chat",
        "provenance": "direct",
        "pending_approval": None,
    }

    # Start queue worker
    queue.start_worker()

    with patch("backend.app.services.chat_service.ChatService.chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = mock_chat_result

        # Reset cooldown on the model to simulate cooldown ending
        cooldown_tracker._get_window("gemini", "test-chat").cooldown_until = time.time() - 1

        await queue.enqueue(req)

        # Wait for auto-retry future to be resolved by background worker
        result = await asyncio.wait_for(future, timeout=3.0)
        assert result["content"] == "Retried successfully after cooldown"
        assert mock_chat.called

    queue.stop_worker()
