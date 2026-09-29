from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import compute_args_hash
from backend.app.db.models import Approval, CommandLog, ToolCall


def test_compute_args_hash_canonicalization() -> None:
    args_a = {"app_name": "notepad", "delay": 5, "silent": True}
    args_b = {"silent": True, "delay": 5, "app_name": "notepad"}  # Different order

    hash_a = compute_args_hash(args_a)
    hash_b = compute_args_hash(args_b)

    # Hashes must be identical regardless of key order
    assert hash_a == hash_b
    assert len(hash_a) == 64  # SHA-256 hex length


def test_compute_args_hash_detects_tampering() -> None:
    original_args = {"app_name": "notepad", "path": "C:\\Windows\\notepad.exe"}
    tampered_args = {"app_name": "notepad", "path": "C:\\Windows\\cmd.exe"}  # Substituted

    hash_original = compute_args_hash(original_args)
    hash_tampered = compute_args_hash(tampered_args)

    assert hash_original != hash_tampered


@pytest.mark.asyncio
async def test_approval_record_binding(db_session: AsyncSession) -> None:
    # 1. Create a tool call
    tool_args = {"target": "calc.exe"}
    args_hash = compute_args_hash(tool_args)

    tool_call = ToolCall(
        skill_name="open_app",
        arguments_json='{"target": "calc.exe"}',
        status="awaiting_approval",
    )
    db_session.add(tool_call)
    await db_session.flush()

    # 2. Create approval bound to tool_call and args_hash
    expires_at = datetime.now(UTC) + timedelta(seconds=60)
    approval = Approval(
        tool_call_id=tool_call.id,
        args_hash=args_hash,
        status="pending",
        expires_at=expires_at,
    )
    db_session.add(approval)
    await db_session.flush()

    # 3. Create command_log linked to approval
    log = CommandLog(
        request_id="req_test_12345",
        approval_id=approval.id,
        skill_name="open_app",
        permission_tier="CONFIRM",
        provenance="direct",
        arguments_json='{"target": "calc.exe"}',
        status="success",
    )
    db_session.add(log)
    await db_session.commit()

    from sqlalchemy.orm import selectinload

    # 4. Verify relations with explicit async loading
    res = await db_session.execute(
        select(Approval)
        .options(selectinload(Approval.command_logs))
        .where(Approval.id == approval.id)
    )
    saved_approval = res.scalar_one()
    assert saved_approval.args_hash == args_hash
    assert saved_approval.tool_call_id == tool_call.id
    assert len(saved_approval.command_logs) == 1
    assert saved_approval.command_logs[0].request_id == "req_test_12345"


def test_approval_rejects_expired() -> None:
    from backend.app.core.exceptions import ValidationFailedError
    from backend.app.core.security import validate_approval_state

    past_time = datetime.now(UTC) - timedelta(seconds=10)
    with pytest.raises(ValidationFailedError, match="expired"):
        validate_approval_state(approval_status="pending", expires_at=past_time)


def test_approval_rejects_reuse_or_duplicate_decision() -> None:
    from backend.app.core.exceptions import ValidationFailedError
    from backend.app.core.security import validate_approval_state

    future_time = datetime.now(UTC) + timedelta(minutes=1)

    # Trying to decide an already approved request must fail
    with pytest.raises(ValidationFailedError, match="already in 'approved' state"):
        validate_approval_state(approval_status="approved", expires_at=future_time)

    # Trying to decide an already denied request must fail
    with pytest.raises(ValidationFailedError, match="already in 'denied' state"):
        validate_approval_state(approval_status="denied", expires_at=future_time)
