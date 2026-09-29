from datetime import UTC, datetime
from typing import Any

from backend.app.skills.base import BaseSkill, SkillContext, SkillManifest, SkillResult


class DateTimeSkill(BaseSkill):
    """Provides current time, date, day of week, and timezone information."""

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="datetime",
            description="Retrieve current system date, time, timezone, and day of week on the host machine.",
            default_tier="SAFE",
            default_autonomy="auto",
            timeout_seconds=5,
            parameters_schema={
                "type": "object",
                "properties": {
                    "format": {
                        "type": "string",
                        "description": "Optional strftime format string (e.g. '%Y-%m-%d %H:%M:%S', '%A, %B %d, %Y'). Default is full ISO format.",
                    }
                },
                "additionalProperties": False,
            },
        )

    async def execute(self, arguments: dict[str, Any], _context: SkillContext) -> SkillResult:
        now_utc = datetime.now(UTC)
        now_local = datetime.now().astimezone()

        fmt = arguments.get("format")
        formatted = now_local.strftime(fmt) if fmt else now_local.isoformat()

        tz_name = now_local.tzname() or "Local"
        tz_offset = now_local.strftime("%z")

        data = {
            "iso_local": now_local.isoformat(),
            "iso_utc": now_utc.isoformat(),
            "formatted": formatted,
            "date": now_local.strftime("%Y-%m-%d"),
            "time": now_local.strftime("%H:%M:%S"),
            "day_of_week": now_local.strftime("%A"),
            "timezone": tz_name,
            "timezone_offset": tz_offset,
            "epoch_timestamp": now_utc.timestamp(),
        }

        return SkillResult(success=True, data=data)
