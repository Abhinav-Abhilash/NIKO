import asyncio
import contextlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import psutil
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.core.events import EventBus, get_event_bus
from backend.app.core.exceptions import NotFoundError, ValidationFailedError
from backend.app.core.logging import get_logger
from backend.app.db.models import ScheduledTask, User
from backend.app.db.session import get_session_maker
from backend.app.repositories.scheduled_task_repository import ScheduledTaskRepository
from backend.app.skills.base import SkillContext

logger = get_logger("task_scheduler_service")


CRON_SHORTHANDS: dict[str, str] = {
    "@hourly": "0 * * * *",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@weekly": "0 0 * * 0",
    "@monthly": "0 0 1 * *",
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
}


def parse_cron_field(field_str: str, min_val: int, max_val: int) -> set[int]:
    """Parse a single cron field expression into a set of matching integer values."""
    field_str = field_str.strip()
    if not field_str:
        raise ValidationFailedError("Cron field cannot be empty.")

    result: set[int] = set()

    for part in field_str.split(","):
        part = part.strip()
        if not part:
            continue

        step = 1
        if "/" in part:
            range_part, step_str = part.split("/", 1)
            try:
                step = int(step_str)
                if step <= 0:
                    raise ValueError
            except ValueError as exc:
                raise ValidationFailedError(f"Invalid cron step '{step_str}'.") from exc
        else:
            range_part = part

        if range_part == "*":
            start, end = min_val, max_val
        elif "-" in range_part:
            start_str, end_str = range_part.split("-", 1)
            try:
                start, end = int(start_str), int(end_str)
                if start > end or start < min_val or end > max_val:
                    raise ValueError
            except ValueError as exc:
                raise ValidationFailedError(f"Invalid cron range '{range_part}'.") from exc
        else:
            try:
                start = end = int(range_part)
                if start < min_val or start > max_val:
                    raise ValueError
            except ValueError as exc:
                raise ValidationFailedError(f"Invalid cron value '{range_part}'.") from exc

        result.update(range(start, end + 1, step))

    return result


def cron_matches(dt: datetime, cron_expr: str) -> bool:
    """Evaluate whether a given UTC datetime satisfies a 5-part cron expression."""
    expr = CRON_SHORTHANDS.get(cron_expr.strip(), cron_expr.strip())
    fields = expr.split()
    if len(fields) != 5:
        raise ValidationFailedError(f"Cron expression must have 5 fields, got {len(fields)}: '{expr}'")

    minutes = parse_cron_field(fields[0], 0, 59)
    hours = parse_cron_field(fields[1], 0, 23)
    doms = parse_cron_field(fields[2], 1, 31)
    months = parse_cron_field(fields[3], 1, 12)
    dows = parse_cron_field(fields[4], 0, 7)

    # Convert python weekday (0=Mon, 6=Sun) to cron weekday (0=Sun, 1=Mon, ..., 6=Sat)
    py_dow = dt.weekday()
    cron_dow = (py_dow + 1) % 7

    if dt.minute not in minutes:
        return False
    if dt.hour not in hours:
        return False
    if dt.day not in doms:
        return False
    if dt.month not in months:
        return False
    return cron_dow in dows or (cron_dow == 0 and 7 in dows)


def compute_next_cron_run(
    cron_expr: str,
    base_time: datetime,
    max_search_minutes: int = 525600,
) -> datetime:
    """Find the next future UTC minute satisfying the cron expression."""
    if base_time.tzinfo is None:
        base_time = base_time.replace(tzinfo=UTC)

    curr = base_time.replace(second=0, microsecond=0) + timedelta(minutes=1)

    for _ in range(max_search_minutes):
        if cron_matches(curr, cron_expr):
            return curr
        curr += timedelta(minutes=1)

    raise ValidationFailedError(f"Could not calculate next run for cron '{cron_expr}' within limit.")


class TaskSchedulerService:
    """
    Manages persistent scheduled agent hooks and proactive suggestions.
    Runs a non-blocking background polling worker that triggers due tasks
    and broadcasts proactive alerts over EventBus / WebSocket.
    """

    def __init__(
        self,
        db_session: AsyncSession | None = None,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        event_bus: EventBus | None = None,
        poll_interval_seconds: float = 5.0,
    ) -> None:
        self.db_session = db_session
        self.session_factory = session_factory or get_session_maker()
        self.event_bus = event_bus or get_event_bus()
        self.poll_interval = poll_interval_seconds
        self._worker_task: asyncio.Task[None] | None = None
        self._running = False
        self._proactive_cooldowns: dict[str, datetime] = {}

    def calculate_next_run(
        self,
        schedule_type: str,
        base_time: datetime,
        interval_seconds: int | None = None,
        cron_expression: str | None = None,
    ) -> datetime | None:
        """Compute the next execution time for a task based on its schedule parameters."""
        if schedule_type == "once":
            return None
        if schedule_type == "interval":
            sec = interval_seconds or 60
            return base_time + timedelta(seconds=sec)
        if schedule_type == "cron":
            if not cron_expression:
                raise ValidationFailedError("Cron expression required for cron schedule type.")
            return compute_next_cron_run(cron_expression, base_time)
        raise ValidationFailedError(f"Unknown schedule type '{schedule_type}'.")

    async def create_task(
        self,
        name: str,
        schedule_type: str,
        action_name: str,
        user_id: str | None = None,
        next_run_at: datetime | None = None,
        description: str | None = None,
        cron_expression: str | None = None,
        interval_seconds: int | None = None,
        action_type: str = "skill",
        payload: dict[str, Any] | None = None,
        status: str = "active",
        session: AsyncSession | None = None,
    ) -> ScheduledTask:
        """Create and persist a new scheduled task."""
        if not name.strip():
            raise ValidationFailedError("Task name cannot be empty.")
        if schedule_type not in ("interval", "cron", "once"):
            raise ValidationFailedError(f"Invalid schedule_type '{schedule_type}'.")
        if action_type not in ("skill", "chat_prompt", "notification"):
            raise ValidationFailedError(f"Invalid action_type '{action_type}'.")

        now = datetime.now(UTC)

        # Validate schedule parameters and determine initial next_run_at
        if schedule_type == "cron":
            if not cron_expression:
                raise ValidationFailedError("Cron expression required for cron tasks.")
            computed_next = compute_next_cron_run(cron_expression, now)
            target_next = next_run_at or computed_next
        elif schedule_type == "interval":
            if not interval_seconds or interval_seconds < 1:
                raise ValidationFailedError("interval_seconds must be a positive integer.")
            target_next = next_run_at or (now + timedelta(seconds=interval_seconds))
        else:  # once
            if not next_run_at:
                raise ValidationFailedError("next_run_at timestamp is required for one-time tasks.")
            if next_run_at.tzinfo is None:
                next_run_at = next_run_at.replace(tzinfo=UTC)
            target_next = next_run_at

        target_session = session or self.db_session
        should_commit = False
        if not target_session:
            target_session = self.session_factory()
            should_commit = True

        try:
            if not user_id:
                user_res = await target_session.execute(select(User).limit(1))
                first_user = user_res.scalar_one_or_none()
                if first_user:
                    user_id = first_user.id
                else:
                    default_user = User(
                        username="operator",
                        password_hash="system_managed",
                        role="owner",
                    )
                    target_session.add(default_user)
                    await target_session.flush()
                    user_id = default_user.id

            repo = ScheduledTaskRepository(target_session)
            task = await repo.create(
                user_id=user_id,
                name=name.strip(),
                description=description.strip() if description else None,
                schedule_type=schedule_type,
                cron_expression=cron_expression,
                interval_seconds=interval_seconds,
                action_type=action_type,
                action_name=action_name.strip(),
                payload_json=json.dumps(payload or {}),
                status=status,
                next_run_at=target_next,
            )
            if should_commit:
                await target_session.commit()
                await target_session.refresh(task)
            else:
                await target_session.flush()

            logger.info(
                "Created scheduled task",
                task_id=task.id,
                name=task.name,
                schedule_type=task.schedule_type,
                next_run_at=task.next_run_at.isoformat(),
            )
            return task
        finally:
            if should_commit and target_session:
                await target_session.close()

    async def list_tasks(
        self,
        user_id: str | None = None,
        status: str | None = None,
        session: AsyncSession | None = None,
    ) -> list[ScheduledTask]:
        """List tasks optionally filtered by user and status."""
        target_session = session or self.db_session
        should_close = False
        if not target_session:
            target_session = self.session_factory()
            should_close = True

        try:
            repo = ScheduledTaskRepository(target_session)
            return await repo.list_tasks(user_id=user_id, status=status)
        finally:
            if should_close and target_session:
                await target_session.close()

    async def get_task(
        self,
        task_id: str,
        user_id: str | None = None,
        session: AsyncSession | None = None,
    ) -> ScheduledTask:
        """Retrieve task by ID."""
        target_session = session or self.db_session
        should_close = False
        if not target_session:
            target_session = self.session_factory()
            should_close = True

        try:
            repo = ScheduledTaskRepository(target_session)
            task = await repo.get_by_id(task_id, user_id=user_id)
            if not task:
                raise NotFoundError(f"Scheduled task '{task_id}' was not found.")
            return task
        finally:
            if should_close and target_session:
                await target_session.close()

    async def update_task(
        self,
        task_id: str,
        user_id: str | None = None,
        status: str | None = None,
        session: AsyncSession | None = None,
        **kwargs: Any,
    ) -> ScheduledTask:
        """Update task status or parameters."""
        target_session = session or self.db_session
        should_commit = False
        if not target_session:
            target_session = self.session_factory()
            should_commit = True

        try:
            repo = ScheduledTaskRepository(target_session)
            task = await repo.get_by_id(task_id, user_id=user_id)
            if not task:
                raise NotFoundError(f"Scheduled task '{task_id}' was not found.")

            if status:
                if status not in ("active", "paused", "completed", "failed"):
                    raise ValidationFailedError(f"Invalid status '{status}'.")
                task.status = status

            for k, v in kwargs.items():
                if hasattr(task, k):
                    setattr(task, k, v)

            if should_commit:
                await target_session.commit()
                await target_session.refresh(task)
            else:
                await target_session.flush()

            logger.info("Updated scheduled task", task_id=task_id, status=task.status)
            return task
        finally:
            if should_commit and target_session:
                await target_session.close()

    async def delete_task(
        self,
        task_id: str,
        user_id: str | None = None,
        session: AsyncSession | None = None,
    ) -> None:
        """Delete a scheduled task."""
        target_session = session or self.db_session
        should_commit = False
        if not target_session:
            target_session = self.session_factory()
            should_commit = True

        try:
            repo = ScheduledTaskRepository(target_session)
            task = await repo.get_by_id(task_id, user_id=user_id)
            if not task:
                raise NotFoundError(f"Scheduled task '{task_id}' was not found.")

            await repo.delete(task)
            if should_commit:
                await target_session.commit()
            else:
                await target_session.flush()
            logger.info("Deleted scheduled task", task_id=task_id)
        finally:
            if should_commit and target_session:
                await target_session.close()

    # ---------------------------------------------------------
    # Execution & Proactive Suggester Engine
    # ---------------------------------------------------------

    async def execute_task_action(self, task: ScheduledTask, session: AsyncSession) -> dict[str, Any]:
        """Execute the configured action for a scheduled task."""
        try:
            payload = json.loads(task.payload_json) if task.payload_json else {}
        except Exception:
            payload = {}

        result: dict[str, Any] = {}

        if task.action_type == "skill":
            from backend.app.services.skill_service import SkillService
            skill_service = SkillService(session)
            ctx = SkillContext(
                request_id=f"sched_{task.id}_{int(datetime.now(UTC).timestamp())}",
                user_id=task.user_id,
                provenance="direct",
            )
            skill_res = await skill_service.execute_skill(
                name=task.action_name,
                arguments=payload,
                context=ctx,
                elevated_mode=True,
            )
            result = {
                "success": skill_res.success,
                "data": skill_res.data,
                "error": skill_res.error,
            }

        elif task.action_type == "notification":
            await self.event_bus.publish(
                "notifications",
                "scheduled_notification",
                {
                    "task_id": task.id,
                    "title": task.name,
                    "payload": payload,
                },
            )
            result = {"success": True, "dispatched": "notification"}

        elif task.action_type == "chat_prompt":
            await self.event_bus.publish(
                "task",
                "agent_prompt",
                {
                    "task_id": task.id,
                    "name": task.name,
                    "prompt": payload.get("prompt", task.name),
                },
            )
            result = {"success": True, "dispatched": "chat_prompt"}

        elif task.action_type == "backup":
            from backend.app.services.backup_service import BackupService
            backup_service = BackupService()
            backup_res = backup_service.create_backup()
            result = {"success": True, "backup": backup_res}

        elif task.action_type == "maintenance":
            from backend.app.services.janitor_service import JanitorService
            janitor = JanitorService()
            maint_res = janitor.run_maintenance_cycle()
            result = {"success": True, "maintenance": maint_res}

        return result


    async def check_and_run_due_tasks(self) -> int:
        """Poll and execute all currently due scheduled tasks."""
        now = datetime.now(UTC)
        executed_count = 0

        async with self.session_factory() as session:
            try:
                repo = ScheduledTaskRepository(session)
                due_tasks = await repo.list_due_tasks(now=now, limit=20)

                for task in due_tasks:
                    logger.info("Triggering scheduled task", task_id=task.id, name=task.name)
                    await self.event_bus.publish(
                        "task",
                        "triggered",
                        {
                            "task_id": task.id,
                            "name": task.name,
                            "action_type": task.action_type,
                            "action_name": task.action_name,
                        },
                    )

                    # Execute the task action
                    try:
                        action_res = await self.execute_task_action(task, session)
                        res_json = json.dumps(action_res)
                    except Exception as exc:
                        logger.error("Error executing task action", task_id=task.id, error=str(exc))
                        res_json = json.dumps({"success": False, "error": str(exc)})

                    # Calculate next run
                    next_run: datetime | None = None
                    try:
                        next_run = self.calculate_next_run(
                            schedule_type=task.schedule_type,
                            base_time=now,
                            interval_seconds=task.interval_seconds,
                            cron_expression=task.cron_expression,
                        )
                    except Exception as exc:
                        logger.error("Failed calculating next run", task_id=task.id, error=str(exc))

                    await repo.advance_run(
                        task=task,
                        next_run_at=next_run,
                        result_json=res_json,
                        status="active" if next_run is not None else "completed",
                    )

                    await self.event_bus.publish(
                        "task",
                        "completed",
                        {
                            "task_id": task.id,
                            "name": task.name,
                            "total_runs": task.total_runs,
                            "next_run_at": next_run.isoformat() if next_run else None,
                        },
                    )
                    executed_count += 1

                if executed_count > 0:
                    await session.commit()

            except Exception as exc:
                await session.rollback()
                logger.error("Error during scheduled task execution loop", error=str(exc))

        return executed_count

    async def check_proactive_suggestions(self) -> int:
        """
        Evaluate host telemetry and upcoming items to generate proactive suggestions.
        Guarded by cooldowns to prevent notification spam.
        """
        now = datetime.now(UTC)
        suggestions_sent = 0

        # 1. System telemetry alerts (RAM / CPU threshold check)
        ram_key = "proactive_ram_alert"
        ram_cooldown = self._proactive_cooldowns.get(ram_key)
        if not ram_cooldown or now > ram_cooldown:
            try:
                mem = psutil.virtual_memory()
                if mem.percent >= 90.0:
                    await self.event_bus.publish(
                        "task",
                        "proactive_suggestion",
                        {
                            "type": "system_resource_alert",
                            "severity": "warning",
                            "title": "High Memory Usage",
                            "detail": f"System RAM utilization is at {mem.percent:.1f}%. Would you like NIKO to inspect memory-heavy processes?",
                        },
                    )
                    self._proactive_cooldowns[ram_key] = now + timedelta(minutes=10)
                    suggestions_sent += 1
            except Exception as exc:
                logger.debug("Proactive RAM telemetry check skipped", error=str(exc))

        # 2. Disk space check
        disk_key = "proactive_disk_alert"
        disk_cooldown = self._proactive_cooldowns.get(disk_key)
        if not disk_cooldown or now > disk_cooldown:
            try:
                disk = psutil.disk_usage("/")
                if disk.percent >= 92.0:
                    await self.event_bus.publish(
                        "task",
                        "proactive_suggestion",
                        {
                            "type": "disk_alert",
                            "severity": "warning",
                            "title": "Low Storage Space",
                            "detail": f"Host drive storage is {disk.percent:.1f}% full. Consider generating a storage clean report.",
                        },
                    )
                    self._proactive_cooldowns[disk_key] = now + timedelta(hours=1)
                    suggestions_sent += 1
            except Exception as exc:
                logger.debug("Proactive disk check skipped", error=str(exc))

        return suggestions_sent

    async def _worker_loop(self) -> None:
        """Continuous background scheduling and proactive analysis loop."""
        while self._running:
            try:
                await self.check_and_run_due_tasks()
                await self.check_proactive_suggestions()
            except Exception as exc:
                logger.error("Unhandled error in task scheduler worker", error=str(exc))

            try:
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break

    async def start_background_worker(self) -> None:
        """Start the background task scheduler worker loop."""
        if not self._running:
            self._running = True
            self._worker_task = asyncio.create_task(self._worker_loop())
            logger.info("Started background task scheduler worker", interval=self.poll_interval)

    async def stop_background_worker(self) -> None:
        """Stop the background task scheduler worker loop."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._worker_task
            self._worker_task = None
            logger.info("Stopped background task scheduler worker")


_global_task_scheduler_service: TaskSchedulerService | None = None


def get_task_scheduler_service(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> TaskSchedulerService:
    global _global_task_scheduler_service
    if _global_task_scheduler_service is None:
        _global_task_scheduler_service = TaskSchedulerService(
            session_factory=session_factory or get_session_maker()
        )
    return _global_task_scheduler_service
