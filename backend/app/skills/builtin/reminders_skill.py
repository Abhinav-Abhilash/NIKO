from datetime import UTC, datetime, timedelta
from typing import Any

from backend.app.core.exceptions import ValidationFailedError
from backend.app.services.reminder_service import ReminderService, get_reminder_service
from backend.app.skills.base import BaseSkill, SkillContext, SkillManifest, SkillResult


class RemindersSkill(BaseSkill):
    """Manages scheduled alarms and reminders in persistent storage."""

    def __init__(self, reminder_service: ReminderService | None = None) -> None:
        self.reminder_service = reminder_service

    def _get_service(self) -> ReminderService:
        return self.reminder_service or get_reminder_service()

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="reminders",
            description=(
                "Schedule, query, list, or cancel persistent alarms and reminders. "
                "Fires notifications to the user interface at the scheduled time."
            ),
            default_tier="CONFIRM",
            default_autonomy="auto+log",
            timeout_seconds=10,
            parameters_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["create", "list", "cancel", "get"],
                        "description": "Operation to perform on reminders.",
                    },
                    "title": {
                        "type": "string",
                        "description": "Short title or topic of the reminder (required for create).",
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional notes or details for the reminder.",
                    },
                    "trigger_at": {
                        "type": "string",
                        "description": (
                            "ISO 8601 formatted datetime string when reminder should trigger "
                            "(e.g. '2026-09-30T15:30:00Z')."
                        ),
                    },
                    "in_minutes": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Alternative relative offset in minutes from now (e.g. 10 for in 10 minutes).",
                    },
                    "reminder_id": {
                        "type": "string",
                        "description": "Unique ID of the reminder to get or cancel.",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["scheduled", "fired", "cancelled", "all"],
                        "default": "scheduled",
                        "description": "Filter status for listing reminders (default 'scheduled').",
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
            title = (arguments.get("title") or "").strip()
            if not title:
                raise ValidationFailedError("Parameter 'title' is required to create a reminder.")

            description = arguments.get("description")
            trigger_at_str = arguments.get("trigger_at")
            in_minutes = arguments.get("in_minutes")

            target_dt: datetime
            if in_minutes is not None and int(in_minutes) > 0:
                target_dt = datetime.now(UTC) + timedelta(minutes=int(in_minutes))
            elif trigger_at_str:
                try:
                    parsed = datetime.fromisoformat(trigger_at_str.replace("Z", "+00:00"))
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=UTC)
                    target_dt = parsed
                except Exception as exc:
                    raise ValidationFailedError(f"Invalid ISO datetime format for 'trigger_at': {exc}") from exc
            else:
                raise ValidationFailedError("Either 'trigger_at' or 'in_minutes' must be specified.")

            reminder = await service.create_reminder(
                title=title,
                trigger_at=target_dt,
                description=description,
                user_id=context.user_id,
            )

            return SkillResult(
                success=True,
                data={
                    "action": "create",
                    "id": reminder.id,
                    "title": reminder.title,
                    "description": reminder.description,
                    "trigger_at": reminder.trigger_at.isoformat(),
                    "status": reminder.status,
                },
            )

        elif action == "list":
            status_filter = arguments.get("status") or "scheduled"
            reminders = await service.list_reminders(
                user_id=context.user_id,
                status=status_filter,
            )
            return SkillResult(
                success=True,
                data={
                    "action": "list",
                    "count": len(reminders),
                    "reminders": [
                        {
                            "id": r.id,
                            "title": r.title,
                            "description": r.description,
                            "trigger_at": r.trigger_at.isoformat(),
                            "status": r.status,
                            "created_at": r.created_at.isoformat(),
                        }
                        for r in reminders
                    ],
                },
            )

        elif action == "cancel":
            reminder_id = arguments.get("reminder_id")
            if not reminder_id:
                raise ValidationFailedError("Parameter 'reminder_id' is required to cancel a reminder.")

            reminder = await service.cancel_reminder(
                reminder_id=reminder_id,
                user_id=context.user_id,
            )
            return SkillResult(
                success=True,
                data={
                    "action": "cancel",
                    "id": reminder.id,
                    "title": reminder.title,
                    "status": reminder.status,
                },
            )

        elif action == "get":
            reminder_id = arguments.get("reminder_id")
            if not reminder_id:
                raise ValidationFailedError("Parameter 'reminder_id' is required to get a reminder.")

            reminder = await service.get_reminder(reminder_id=reminder_id)
            return SkillResult(
                success=True,
                data={
                    "action": "get",
                    "id": reminder.id,
                    "title": reminder.title,
                    "description": reminder.description,
                    "trigger_at": reminder.trigger_at.isoformat(),
                    "status": reminder.status,
                },
            )

        else:
            raise ValidationFailedError(f"Unsupported reminder action: '{action}'")
