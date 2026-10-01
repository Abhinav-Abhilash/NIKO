import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.core.events import EventBus
from backend.app.core.exceptions import NotFoundError, ValidationFailedError
from backend.app.core.security import hash_password
from backend.app.db.models import User
from backend.app.services.task_scheduler_service import (
    TaskSchedulerService,
    compute_next_cron_run,
    cron_matches,
    parse_cron_field,
)


def test_cron_field_parsing() -> None:
    # Wildcard
    assert parse_cron_field("*", 0, 5) == {0, 1, 2, 3, 4, 5}

    # Step
    assert parse_cron_field("*/15", 0, 59) == {0, 15, 30, 45}

    # Range and comma list
    assert parse_cron_field("1-3,5", 0, 10) == {1, 2, 3, 5}

    # Range with step
    assert parse_cron_field("10-20/5", 0, 30) == {10, 15, 20}

    # Negative validation
    with pytest.raises(ValidationFailedError, match="Invalid cron value"):
        parse_cron_field("99", 0, 59)

    with pytest.raises(ValidationFailedError, match="Invalid cron range"):
        parse_cron_field("20-10", 0, 59)

    with pytest.raises(ValidationFailedError, match="Invalid cron step"):
        parse_cron_field("*/0", 0, 59)


def test_cron_matching_and_computation() -> None:
    # 2026-10-01 is a Thursday (dow=4 in python, dow=4 in 1-based cron)
    base = datetime(2026, 10, 1, 14, 0, 0, tzinfo=UTC)

    # Next hourly run
    next_hour = compute_next_cron_run("@hourly", base)
    assert next_hour == datetime(2026, 10, 1, 15, 0, 0, tzinfo=UTC)

    # Daily run at 09:00
    next_daily = compute_next_cron_run("0 9 * * *", base)
    assert next_daily == datetime(2026, 10, 2, 9, 0, 0, tzinfo=UTC)

    # Invalid format
    with pytest.raises(ValidationFailedError, match="must have 5 fields"):
        cron_matches(base, "0 9 * *")


@pytest.mark.asyncio
async def test_scheduler_service_crud_lifecycle(
    db_session: AsyncSession,
) -> None:
    user = User(username="sched_user_crud", password_hash=hash_password("pw123"), role="owner")
    db_session.add(user)
    await db_session.flush()

    service = TaskSchedulerService(db_session=db_session)

    # 1. Create task
    task = await service.create_task(
        user_id=user.id,
        name="Hourly Stats",
        schedule_type="interval",
        interval_seconds=3600,
        action_name="system_stats",
        payload={"detail": True},
    )
    assert task.id is not None
    assert task.name == "Hourly Stats"

    # 2. List tasks
    tasks = await service.list_tasks(user_id=user.id)
    assert len(tasks) == 1

    # 3. Get task
    fetched = await service.get_task(task.id, user_id=user.id)
    assert fetched.name == "Hourly Stats"

    # 4. Update task
    updated = await service.update_task(task.id, user_id=user.id, status="paused")
    assert updated.status == "paused"

    # 5. Delete task
    await service.delete_task(task.id, user_id=user.id)
    with pytest.raises(NotFoundError):
        await service.get_task(task.id, user_id=user.id)


@pytest.mark.asyncio
async def test_scheduler_execute_due_tasks_and_events(
    db_session: AsyncSession,
) -> None:
    from collections.abc import AsyncIterator
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def mock_session_factory() -> AsyncIterator[AsyncSession]:
        yield db_session

    bus = EventBus(maxsize=50)
    service = TaskSchedulerService(
        db_session=db_session,
        session_factory=mock_session_factory,  # type: ignore[arg-type]
        event_bus=bus,
    )

    user = User(username="sched_user_exec", password_hash=hash_password("pw123"), role="owner")
    db_session.add(user)
    await db_session.flush()

    past_time = datetime.now(UTC) - timedelta(minutes=5)

    # Recurring interval task
    t_interval = await service.create_task(
        user_id=user.id,
        name="Scheduled Interval Stats",
        schedule_type="interval",
        interval_seconds=60,
        action_type="skill",
        action_name="system_stats",
        next_run_at=past_time,
    )

    # One-time notification task
    t_once = await service.create_task(
        user_id=user.id,
        name="Single Notification",
        schedule_type="once",
        action_type="notification",
        action_name="alert",
        payload={"message": "System check complete"},
        next_run_at=past_time,
    )

    triggered_events = []
    completed_events = []

    async def collect_events() -> None:
        async for ev in bus.subscribe(topic="task:triggered"):
            triggered_events.append(ev)
            if len(triggered_events) >= 2:
                break

    async def collect_completed() -> None:
        async for ev in bus.subscribe(topic="task:completed"):
            completed_events.append(ev)
            if len(completed_events) >= 2:
                break

    t_trig = asyncio.create_task(collect_events())
    t_comp = asyncio.create_task(collect_completed())
    await asyncio.sleep(0.01)

    executed_count = await service.check_and_run_due_tasks()
    assert executed_count == 2

    await asyncio.wait_for(asyncio.gather(t_trig, t_comp), timeout=3.0)
    assert len(triggered_events) == 2
    assert len(completed_events) == 2

    # Verify task state in database
    refreshed_interval = await service.get_task(t_interval.id)
    assert refreshed_interval.total_runs == 1
    assert refreshed_interval.status == "active"
    assert refreshed_interval.next_run_at > datetime.now(UTC)

    refreshed_once = await service.get_task(t_once.id)
    assert refreshed_once.total_runs == 1
    assert refreshed_once.status == "completed"


@pytest.mark.asyncio
async def test_scheduler_proactive_suggestions_and_cooldown(
    test_engine: Any,
) -> None:
    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    bus = EventBus(maxsize=20)
    service = TaskSchedulerService(session_factory=session_factory, event_bus=bus)

    proactive_events = []

    async def listener() -> None:
        async for ev in bus.subscribe(topic="task:proactive_suggestion"):
            proactive_events.append(ev)
            break

    task_listener = asyncio.create_task(listener())
    await asyncio.sleep(0.01)

    # Mock high RAM utilization (95%)
    mock_mem = MagicMock()
    mock_mem.percent = 95.0

    mock_disk = MagicMock()
    mock_disk.percent = 50.0

    with patch("psutil.virtual_memory", return_value=mock_mem), patch("psutil.disk_usage", return_value=mock_disk):
        count1 = await service.check_proactive_suggestions()
        assert count1 == 1

        # Second call immediately should be suppressed by cooldown
        count2 = await service.check_proactive_suggestions()
        assert count2 == 0

    await asyncio.wait_for(task_listener, timeout=2.0)
    assert len(proactive_events) == 1
    assert proactive_events[0].payload["type"] == "system_resource_alert"
    assert "95.0%" in proactive_events[0].payload["detail"]


@pytest.mark.asyncio
async def test_scheduler_worker_start_and_stop(
    test_engine: Any,
) -> None:
    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    service = TaskSchedulerService(
        session_factory=session_factory,
        poll_interval_seconds=0.1,
    )
    await service.start_background_worker()
    assert service._running is True
    assert service._worker_task is not None

    await asyncio.sleep(0.15)
    await service.stop_background_worker()
    assert service._running is False
    assert service._worker_task is None

