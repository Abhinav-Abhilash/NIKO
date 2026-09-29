import asyncio
import time
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import get_settings
from backend.app.core.security import create_jwt_token, hash_password
from backend.app.db.models import CommandLog, User
from backend.app.services.skill_service import SkillService
from backend.app.skills.base import BaseSkill, SkillContext, SkillManifest, SkillResult


class MockSafeSkill(BaseSkill):
    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="mock_safe",
            description="Safe test skill",
            default_tier="SAFE",
            default_autonomy="auto",
            timeout_seconds=5,
        )

    async def execute(self, _arguments: dict[str, Any], _context: SkillContext) -> SkillResult:
        return SkillResult(success=True, data={"performed": True})


@pytest.mark.asyncio
async def test_undo_window_delays_execution_until_closed(db_session: AsyncSession) -> None:
    """The undo window delays execution until the window closes without cancel."""
    service = SkillService(db=db_session, undo_window_seconds=0.15)
    service.registry.register(MockSafeSkill())

    ctx = SkillContext(
        request_id="req_delay_test",
        provenance="external_untrusted",  # Triggers requires_toast_undo
    )

    start = time.perf_counter()
    result = await service.execute_skill("mock_safe", {}, ctx)
    elapsed = time.perf_counter() - start

    assert result.success is True
    assert result.data == {"performed": True}
    assert elapsed >= 0.14  # Execution was delayed by the window!


@pytest.mark.asyncio
async def test_undo_window_cancels_execution(db_session: AsyncSession) -> None:
    """If cancel is triggered during the undo window, execution is aborted immediately."""
    service = SkillService(db=db_session, undo_window_seconds=0.5)
    service.registry.register(MockSafeSkill())

    ctx = SkillContext(
        request_id="req_cancel_test",
        provenance="external_untrusted",
    )

    undo_id = f"undo_{ctx.request_id}"

    async def _cancel_after_delay() -> None:
        await asyncio.sleep(0.05)
        cancelled = SkillService.cancel_undo(undo_id)
        assert cancelled is True

    cancel_task = asyncio.create_task(_cancel_after_delay())
    start = time.perf_counter()
    result = await service.execute_skill("mock_safe", {}, ctx)
    elapsed = time.perf_counter() - start
    await cancel_task

    assert result.success is False
    assert result.error == "CANCELLED_BY_USER"
    assert elapsed < 0.35  # Cancelled before full window expired!

    # Check audit log reflects cancellation
    logs = (
        await db_session.execute(
            select(CommandLog).where(CommandLog.request_id == "req_cancel_test")
        )
    ).scalars().all()
    assert len(logs) == 1
    assert logs[0].status == "cancelled_by_user"


@pytest.mark.asyncio
async def test_cancel_undo_endpoint(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """API endpoint POST /skills/undo/{undo_id}/cancel cancels active undo."""
    # Setup owner
    owner = User(
        username="undo_owner",
        password_hash=hash_password("pw123"),
        role="owner",
    )
    db_session.add(owner)
    await db_session.commit()

    settings = get_settings()
    token = create_jwt_token(
        payload={"sub": owner.id, "username": owner.username, "role": owner.role},
        secret_key=settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Origin": "http://127.0.0.1:5173",
    }

    test_undo_id = "undo_fake_123"
    cancel_event = asyncio.Event()
    SkillService._active_undo_cancels[test_undo_id] = cancel_event

    try:
        res = await async_client.post(
            f"/api/v1/skills/undo/{test_undo_id}/cancel",
            headers=headers,
        )
        assert res.status_code == 200
        assert res.json() == {"undo_id": test_undo_id, "cancelled": True}
        assert cancel_event.is_set() is True
    finally:
        SkillService._active_undo_cancels.pop(test_undo_id, None)
