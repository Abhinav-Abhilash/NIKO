import json
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import ValidationFailedError
from backend.app.core.security import compute_args_hash, create_jwt_token, hash_password
from backend.app.db.models import ToolCall, User
from backend.app.services.approval_service import ApprovalService


@pytest.mark.asyncio
async def test_approval_service_lifecycle_approve(db_session: AsyncSession) -> None:
    # 1. Create a dummy user and tool call
    user = User(username="admin", password_hash=hash_password("admin_pass_123"), role="owner")
    db_session.add(user)
    await db_session.flush()

    args = {"target": "notepad.exe", "options": ["/w"]}
    tool_call = ToolCall(
        skill_name="open_app",
        arguments_json=json.dumps(args),
        status="awaiting_approval",
    )
    db_session.add(tool_call)
    await db_session.flush()

    service = ApprovalService(db_session)

    # 2. Create approval request
    approval = await service.create_approval(
        tool_call_id=tool_call.id,
        arguments=args,
        skill_name="open_app",
        expires_in_seconds=30,
    )
    assert approval.id is not None
    assert approval.status == "pending"
    assert approval.args_hash == compute_args_hash(args)
    assert approval.expires_at > datetime.now(UTC)

    # 3. Respond with 'approve' and matching arguments
    resolved = await service.respond(
        approval_id=approval.id,
        decision="approve",
        user_id=user.id,
        current_arguments=args,
    )
    assert resolved.status == "approved"
    assert resolved.decided_by == user.id
    assert resolved.decided_at is not None
    assert tool_call.status == "running"


@pytest.mark.asyncio
async def test_approval_service_tampered_args_rejected(db_session: AsyncSession) -> None:
    user = User(username="admin2", password_hash=hash_password("admin_pass_123"), role="owner")
    db_session.add(user)
    await db_session.flush()

    args = {"target": "notepad.exe"}
    tool_call = ToolCall(
        skill_name="open_app",
        arguments_json=json.dumps(args),
        status="awaiting_approval",
    )
    db_session.add(tool_call)
    await db_session.flush()

    service = ApprovalService(db_session)
    approval = await service.create_approval(
        tool_call_id=tool_call.id,
        arguments=args,
        skill_name="open_app",
    )

    # Substituted / tampered arguments
    tampered_args = {"target": "powershell.exe", "payload": "rm -rf"}
    with pytest.raises(ValidationFailedError, match="Cryptographic binding failure"):
        await service.respond(
            approval_id=approval.id,
            decision="approve",
            user_id=user.id,
            current_arguments=tampered_args,
        )


@pytest.mark.asyncio
async def test_approval_service_deny(db_session: AsyncSession) -> None:
    user = User(username="admin3", password_hash=hash_password("admin_pass_123"), role="owner")
    db_session.add(user)
    await db_session.flush()

    args = {"target": "calc.exe"}
    tool_call = ToolCall(
        skill_name="open_app",
        arguments_json=json.dumps(args),
        status="awaiting_approval",
    )
    db_session.add(tool_call)
    await db_session.flush()

    service = ApprovalService(db_session)
    approval = await service.create_approval(
        tool_call_id=tool_call.id,
        arguments=args,
        skill_name="open_app",
    )

    resolved = await service.respond(
        approval_id=approval.id,
        decision="deny",
        user_id=user.id,
    )
    assert resolved.status == "denied"
    assert tool_call.status == "rejected"


@pytest.mark.asyncio
async def test_approval_service_expired_cleanup(db_session: AsyncSession) -> None:
    tool_call = ToolCall(
        skill_name="open_app",
        arguments_json="{}",
        status="awaiting_approval",
    )
    db_session.add(tool_call)
    await db_session.flush()

    service = ApprovalService(db_session)
    # Create already expired approval
    approval = await service.create_approval(
        tool_call_id=tool_call.id,
        arguments={},
        expires_in_seconds=-5,
    )
    assert approval.expires_at < datetime.now(UTC)

    count = await service.expire_stale()
    assert count >= 1

    fetched = await service.get_approval(approval.id)
    assert fetched is not None
    assert fetched.status == "expired"


@pytest.mark.asyncio
async def test_approval_api_endpoints_and_reuse_prevention(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    # 1. Seed owner user
    owner = User(
        username="niko_owner",
        password_hash=hash_password("owner_password_123"),
        role="owner",
    )
    db_session.add(owner)
    await db_session.flush()

    from backend.app.config import get_settings

    settings = get_settings()
    access_token = create_jwt_token(
        payload={"sub": owner.id, "username": owner.username, "role": owner.role},
        secret_key=settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
        expires_delta=timedelta(minutes=15),
    )
    headers = {"Authorization": f"Bearer {access_token}"}

    # 2. Seed tool call and approval
    args = {"target": "explorer.exe"}
    tool_call = ToolCall(
        skill_name="open_app",
        arguments_json=json.dumps(args),
        status="awaiting_approval",
    )
    db_session.add(tool_call)
    await db_session.flush()

    service = ApprovalService(db_session)
    approval = await service.create_approval(
        tool_call_id=tool_call.id,
        arguments=args,
        skill_name="open_app",
        expires_in_seconds=30,
    )
    await db_session.commit()

    # 3. GET /api/v1/approvals/pending
    res_pending = await async_client.get("/api/v1/approvals/pending", headers=headers)
    assert res_pending.status_code == 200
    pending_list = res_pending.json()
    assert len(pending_list) >= 1
    assert any(a["id"] == approval.id for a in pending_list)

    # 4. GET /api/v1/approvals/{id}
    res_detail = await async_client.get(f"/api/v1/approvals/{approval.id}", headers=headers)
    assert res_detail.status_code == 200
    assert res_detail.json()["id"] == approval.id
    assert res_detail.json()["status"] == "pending"

    # 5. POST /api/v1/approvals/{id}/respond (Approve)
    res_respond = await async_client.post(
        f"/api/v1/approvals/{approval.id}/respond",
        headers=headers,
        json={"decision": "approve", "arguments": args},
    )
    assert res_respond.status_code == 200
    assert res_respond.json()["status"] == "approved"

    # 6. Re-attempt to respond -> Should fail with 422 (reuse prevention)
    res_reuse = await async_client.post(
        f"/api/v1/approvals/{approval.id}/respond",
        headers=headers,
        json={"decision": "approve", "arguments": args},
    )
    assert res_reuse.status_code == 422
    assert "already in 'approved' state" in res_reuse.json()["error"]["message"]
