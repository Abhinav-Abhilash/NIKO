from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import hash_password
from backend.app.db.models import User
from backend.app.repositories.scheduled_task_repository import ScheduledTaskRepository


@pytest.mark.asyncio
async def test_create_and_get_scheduled_task(db_session: AsyncSession) -> None:
    user = User(username="task_user_1", password_hash=hash_password("pw123"), role="owner")
    db_session.add(user)
    await db_session.flush()

    repo = ScheduledTaskRepository(db_session)
    next_run = datetime.now(UTC) + timedelta(minutes=15)

    task = await repo.create(
        user_id=user.id,
        name="Disk Cleanup",
        description="Run local disk maintenance",
        schedule_type="interval",
        interval_seconds=3600,
        action_type="skill",
        action_name="system_stats",
        payload_json='{"detail": true}',
        next_run_at=next_run,
    )

    assert task.id is not None
    assert task.name == "Disk Cleanup"
    assert task.interval_seconds == 3600
    assert task.total_runs == 0
    assert task.status == "active"

    fetched = await repo.get_by_id(task.id, user_id=user.id)
    assert fetched is not None
    assert fetched.name == "Disk Cleanup"
    assert fetched.user_id == user.id


@pytest.mark.asyncio
async def test_list_tasks_and_filter(db_session: AsyncSession) -> None:
    user = User(username="task_user_2", password_hash=hash_password("pw123"), role="owner")
    db_session.add(user)
    await db_session.flush()

    repo = ScheduledTaskRepository(db_session)
    t1 = await repo.create(
        user_id=user.id,
        name="Task A",
        schedule_type="interval",
        action_name="system_stats",
        next_run_at=datetime.now(UTC) + timedelta(minutes=5),
        status="active",
    )
    t2 = await repo.create(
        user_id=user.id,
        name="Task B",
        schedule_type="cron",
        cron_expression="0 9 * * *",
        action_name="datetime",
        next_run_at=datetime.now(UTC) + timedelta(hours=1),
        status="paused",
    )

    all_tasks = await repo.list_tasks(user_id=user.id)
    assert len(all_tasks) == 2

    active_only = await repo.list_tasks(user_id=user.id, status="active")
    assert len(active_only) == 1
    assert active_only[0].id == t1.id

    paused_only = await repo.list_tasks(user_id=user.id, status="paused")
    assert len(paused_only) == 1
    assert paused_only[0].id == t2.id


@pytest.mark.asyncio
async def test_list_due_tasks(db_session: AsyncSession) -> None:
    user = User(username="task_user_3", password_hash=hash_password("pw123"), role="owner")
    db_session.add(user)
    await db_session.flush()

    repo = ScheduledTaskRepository(db_session)
    now = datetime.now(UTC)

    # Past task (due)
    due_task = await repo.create(
        user_id=user.id,
        name="Due Task",
        schedule_type="interval",
        action_name="system_stats",
        next_run_at=now - timedelta(minutes=2),
        status="active",
    )
    # Future task (not due)
    await repo.create(
        user_id=user.id,
        name="Future Task",
        schedule_type="interval",
        action_name="system_stats",
        next_run_at=now + timedelta(minutes=10),
        status="active",
    )
    # Past paused task (should NOT be returned)
    await repo.create(
        user_id=user.id,
        name="Paused Due Task",
        schedule_type="interval",
        action_name="system_stats",
        next_run_at=now - timedelta(minutes=5),
        status="paused",
    )

    due_list = await repo.list_due_tasks(now=now)
    due_ids = [t.id for t in due_list]
    assert due_task.id in due_ids
    assert len([t for t in due_list if t.user_id == user.id]) == 1


@pytest.mark.asyncio
async def test_advance_run_and_delete(db_session: AsyncSession) -> None:
    user = User(username="task_user_4", password_hash=hash_password("pw123"), role="owner")
    db_session.add(user)
    await db_session.flush()

    repo = ScheduledTaskRepository(db_session)
    now = datetime.now(UTC)

    task = await repo.create(
        user_id=user.id,
        name="Recurring Run",
        schedule_type="interval",
        action_name="system_stats",
        next_run_at=now,
    )

    # Advance recurring run
    next_time = now + timedelta(hours=1)
    advanced = await repo.advance_run(
        task=task,
        next_run_at=next_time,
        result_json='{"status": "ok"}',
    )
    assert advanced.total_runs == 1
    assert advanced.last_run_at is not None
    assert advanced.next_run_at == next_time
    assert advanced.status == "active"
    assert advanced.last_result_json == '{"status": "ok"}'

    # Advance one-time task to completion (next_run_at is None)
    completed = await repo.advance_run(
        task=task,
        next_run_at=None,
        result_json='{"status": "done"}',
    )
    assert completed.total_runs == 2
    assert completed.status == "completed"

    # Delete
    await repo.delete(task)
    assert await repo.get_by_id(task.id) is None
