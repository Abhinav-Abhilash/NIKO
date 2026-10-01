from datetime import UTC, datetime, timedelta
from typing import Any

from backend.app.core.exceptions import ValidationFailedError
from backend.app.services.task_scheduler_service import (
    TaskSchedulerService,
    get_task_scheduler_service,
)
from backend.app.skills.base import BaseSkill, SkillContext, SkillManifest, SkillResult


class ScheduleTaskSkill(BaseSkill):
    """Manages scheduled tasks, cron hooks, and recurring agent jobs."""

    def __init__(self, scheduler_service: TaskSchedulerService | None = None) -> None:
        self.scheduler_service = scheduler_service

    def _get_service(self) -> TaskSchedulerService:
        return self.scheduler_service or get_task_scheduler_service()

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="schedule_task",
            description=(
                "Schedule recurring agent actions, cron jobs, or one-time future tasks. "
                "Supports interval seconds, cron expressions (e.g. '@hourly', '0 9 * * *'), "
                "or one-time deferred execution."
            ),
            default_tier="CONFIRM",
            default_autonomy="ask",
            timeout_seconds=15,
            parameters_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["create", "list", "get", "pause", "resume", "delete"],
                        "description": "Operation to perform on scheduled tasks.",
                    },
                    "name": {
                        "type": "string",
                        "description": "Short, human-readable name of the scheduled task.",
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional notes or details for the task.",
                    },
                    "schedule_type": {
                        "type": "string",
                        "enum": ["interval", "cron", "once"],
                        "default": "interval",
                        "description": "Type of schedule recurrence.",
                    },
                    "interval_seconds": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Interval between runs in seconds (for interval schedule type).",
                    },
                    "cron_expression": {
                        "type": "string",
                        "description": "Standard 5-part cron expression (e.g. '0 9 * * *', '@hourly').",
                    },
                    "run_in_seconds": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Alternative relative offset in seconds for one-time task execution.",
                    },
                    "action_type": {
                        "type": "string",
                        "enum": ["skill", "chat_prompt", "notification"],
                        "default": "skill",
                        "description": "Type of action to execute when task is triggered.",
                    },
                    "action_name": {
                        "type": "string",
                        "description": "Name of the skill to execute or action identifier.",
                    },
                    "payload": {
                        "type": "object",
                        "description": "Parameters to pass to the skill or action payload.",
                    },
                    "task_id": {
                        "type": "string",
                        "description": "Unique ID of the task to get, pause, resume, or delete.",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["active", "paused", "completed", "failed", "all"],
                        "default": "all",
                        "description": "Filter status for listing tasks.",
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        )

    async def execute(self, arguments: dict[str, Any], context: SkillContext) -> SkillResult:
        action = arguments.get("action")
        if not action:
            raise ValidationFailedError("Parameter 'action' is required.")

        service = self._get_service()

        if action == "create":
            name = (arguments.get("name") or "").strip()
            if not name:
                raise ValidationFailedError("Parameter 'name' is required to create a task.")

            schedule_type = arguments.get("schedule_type") or "interval"
            action_name = (arguments.get("action_name") or "").strip()
            if not action_name:
                raise ValidationFailedError("Parameter 'action_name' is required to create a task.")

            action_type = arguments.get("action_type") or "skill"
            payload = arguments.get("payload") or {}
            interval_sec = arguments.get("interval_seconds")
            cron_expr = arguments.get("cron_expression")
            run_in_sec = arguments.get("run_in_seconds")

            next_run_at: datetime | None = None
            if run_in_sec is not None and int(run_in_sec) > 0:
                next_run_at = datetime.now(UTC) + timedelta(seconds=int(run_in_sec))

            task = await service.create_task(
                user_id=context.user_id,
                name=name,
                description=arguments.get("description"),
                schedule_type=schedule_type,
                action_type=action_type,
                action_name=action_name,
                payload=payload,
                interval_seconds=interval_sec,
                cron_expression=cron_expr,
                next_run_at=next_run_at,
            )

            return SkillResult(
                success=True,
                data={
                    "action": "create",
                    "id": task.id,
                    "name": task.name,
                    "schedule_type": task.schedule_type,
                    "action_name": task.action_name,
                    "status": task.status,
                    "next_run_at": task.next_run_at.isoformat(),
                },
            )

        elif action == "list":
            status_filter = arguments.get("status")
            if status_filter == "all":
                status_filter = None

            tasks = await service.list_tasks(user_id=context.user_id, status=status_filter)
            return SkillResult(
                success=True,
                data={
                    "action": "list",
                    "count": len(tasks),
                    "tasks": [
                        {
                            "id": t.id,
                            "name": t.name,
                            "description": t.description,
                            "schedule_type": t.schedule_type,
                            "cron_expression": t.cron_expression,
                            "interval_seconds": t.interval_seconds,
                            "action_type": t.action_type,
                            "action_name": t.action_name,
                            "status": t.status,
                            "next_run_at": t.next_run_at.isoformat(),
                            "last_run_at": t.last_run_at.isoformat() if t.last_run_at else None,
                            "total_runs": t.total_runs,
                        }
                        for t in tasks
                    ],
                },
            )

        elif action == "get":
            task_id = arguments.get("task_id")
            if not task_id:
                raise ValidationFailedError("Parameter 'task_id' is required to get task details.")

            task = await service.get_task(task_id, user_id=context.user_id)
            return SkillResult(
                success=True,
                data={
                    "action": "get",
                    "id": task.id,
                    "name": task.name,
                    "description": task.description,
                    "schedule_type": task.schedule_type,
                    "action_name": task.action_name,
                    "status": task.status,
                    "next_run_at": task.next_run_at.isoformat(),
                    "total_runs": task.total_runs,
                },
            )

        elif action == "pause":
            task_id = arguments.get("task_id")
            if not task_id:
                raise ValidationFailedError("Parameter 'task_id' is required to pause a task.")

            task = await service.update_task(task_id, user_id=context.user_id, status="paused")
            return SkillResult(
                success=True,
                data={
                    "action": "pause",
                    "id": task.id,
                    "status": task.status,
                },
            )

        elif action == "resume":
            task_id = arguments.get("task_id")
            if not task_id:
                raise ValidationFailedError("Parameter 'task_id' is required to resume a task.")

            task = await service.update_task(task_id, user_id=context.user_id, status="active")
            return SkillResult(
                success=True,
                data={
                    "action": "resume",
                    "id": task.id,
                    "status": task.status,
                },
            )

        elif action == "delete":
            task_id = arguments.get("task_id")
            if not task_id:
                raise ValidationFailedError("Parameter 'task_id' is required to delete a task.")

            await service.delete_task(task_id, user_id=context.user_id)
            return SkillResult(
                success=True,
                data={
                    "action": "delete",
                    "id": task_id,
                },
            )

        else:
            raise ValidationFailedError(f"Unsupported schedule_task action: '{action}'")
