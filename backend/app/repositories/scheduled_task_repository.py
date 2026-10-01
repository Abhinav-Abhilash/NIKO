from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import ScheduledTask


class ScheduledTaskRepository:
    """Repository handling database operations for ScheduledTask models."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        user_id: str,
        name: str,
        schedule_type: str,
        action_name: str,
        next_run_at: datetime,
        description: str | None = None,
        cron_expression: str | None = None,
        interval_seconds: int | None = None,
        action_type: str = "skill",
        payload_json: str = "{}",
        status: str = "active",
    ) -> ScheduledTask:
        task = ScheduledTask(
            user_id=user_id,
            name=name,
            description=description,
            schedule_type=schedule_type,
            cron_expression=cron_expression,
            interval_seconds=interval_seconds,
            action_type=action_type,
            action_name=action_name,
            payload_json=payload_json,
            status=status,
            next_run_at=next_run_at,
            total_runs=0,
        )
        self.db.add(task)
        await self.db.flush()
        return task

    async def get_by_id(
        self,
        task_id: str,
        user_id: str | None = None,
    ) -> ScheduledTask | None:
        query = select(ScheduledTask).where(ScheduledTask.id == task_id)
        if user_id:
            query = query.where(ScheduledTask.user_id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_tasks(
        self,
        user_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ScheduledTask]:
        query = select(ScheduledTask)
        if user_id:
            query = query.where(ScheduledTask.user_id == user_id)
        if status:
            query = query.where(ScheduledTask.status == status)
        query = query.order_by(ScheduledTask.next_run_at.asc()).limit(limit).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_due_tasks(
        self,
        now: datetime | None = None,
        limit: int = 20,
    ) -> list[ScheduledTask]:
        current_time = now or datetime.now(UTC)
        query = (
            select(ScheduledTask)
            .where(
                ScheduledTask.status == "active",
                ScheduledTask.next_run_at <= current_time,
            )
            .order_by(ScheduledTask.next_run_at.asc())
            .limit(limit)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update(
        self,
        task: ScheduledTask,
        **kwargs: Any,
    ) -> ScheduledTask:
        for key, value in kwargs.items():
            if hasattr(task, key):
                setattr(task, key, value)
        await self.db.flush()
        return task

    async def advance_run(
        self,
        task: ScheduledTask,
        next_run_at: datetime | None,
        result_json: str | None = None,
        status: str = "active",
    ) -> ScheduledTask:
        task.last_run_at = datetime.now(UTC)
        task.total_runs += 1
        task.last_result_json = result_json
        if next_run_at is not None:
            task.next_run_at = next_run_at
            task.status = status
        else:
            task.status = "completed"
        await self.db.flush()
        return task

    async def delete(self, task: ScheduledTask) -> None:
        await self.db.delete(task)
        await self.db.flush()
