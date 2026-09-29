import asyncio

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.events import EventBus
from backend.app.db.models import ToolCall, User
from backend.app.services.approval_service import ApprovalService


@pytest.mark.asyncio
async def test_approval_resolved_and_chat_tool_call_bus_events(db_session: AsyncSession) -> None:
    bus = EventBus(maxsize=50)
    service = ApprovalService(db_session, event_bus=bus)

    # 1. Setup tool call and user
    user = User(username="bus_owner", password_hash="hash", role="owner")
    db_session.add(user)
    tool_call = ToolCall(skill_name="open_app", arguments_json='{"app": "notepad"}', status="pending")
    db_session.add(tool_call)
    await db_session.flush()

    received_chat_events = []
    received_approval_events = []

    async def chat_listener() -> None:
        async for ev in bus.subscribe(topic="chat:tool_call"):
            received_chat_events.append(ev)
            if len(received_chat_events) >= 2:
                break

    async def approval_listener() -> None:
        async for ev in bus.subscribe(topic="approval:resolved"):
            received_approval_events.append(ev)
            break

    task_chat = asyncio.create_task(chat_listener())
    task_approval = asyncio.create_task(approval_listener())
    await asyncio.sleep(0.01)

    # 2. Create approval -> triggers chat:tool_call
    approval = await service.create_approval(
        tool_call_id=tool_call.id,
        arguments={"app": "notepad"},
        skill_name="open_app",
    )

    # 3. Respond -> triggers approval:resolved and chat:tool_call
    await service.respond(
        approval_id=approval.id,
        decision="approve",
        user_id=user.id,
        current_arguments={"app": "notepad"},
    )

    await asyncio.wait_for(asyncio.gather(task_chat, task_approval), timeout=2.0)

    # Assert approval:resolved was delivered
    assert len(received_approval_events) == 1
    assert received_approval_events[0].topic == "approval"
    assert received_approval_events[0].event_type == "resolved"
    assert received_approval_events[0].payload["approval_id"] == approval.id
    assert received_approval_events[0].payload["status"] == "approved"

    # Assert chat:tool_call was delivered twice (creation and resolution)
    assert len(received_chat_events) == 2
    assert received_chat_events[0].topic == "chat"
    assert received_chat_events[0].event_type == "tool_call"
    assert received_chat_events[0].payload["status"] == "awaiting_approval"
    assert received_chat_events[1].payload["status"] == "running"
    assert received_chat_events[1].payload["decision"] == "approved"
