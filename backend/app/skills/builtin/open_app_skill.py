import asyncio
import os
import subprocess
from pathlib import Path
from typing import Any

from backend.app.core.security import canonicalize_open_app_arguments
from backend.app.skills.base import BaseSkill, SkillContext, SkillManifest, SkillResult


class OpenAppSkill(BaseSkill):
    """Safely launches or focuses allowlisted host applications on Windows."""

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="open_app",
            description="Launch or activate an allowlisted application on the Windows host machine.",
            default_tier="CONFIRM",
            default_autonomy="ask",
            timeout_seconds=15,
            parameters_schema={
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": (
                            "Name or alias of the application to open (e.g. notepad, calc, "
                            "explorer, taskmgr)."
                        ),
                    },
                    "executable_path": {
                        "type": "string",
                        "description": "Optional explicit full path to an authorized executable.",
                    },
                    "arguments": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional command-line arguments to pass to the executable.",
                    },
                },
                "additionalProperties": False,
            },
        )

    async def execute(self, arguments: dict[str, Any], _context: SkillContext) -> SkillResult:
        canonical_args = canonicalize_open_app_arguments(arguments)
        target_exe = Path(canonical_args["executable_path"])
        validated_args = canonical_args["arguments"]
        app_name = canonical_args["app_name"]

        # Non-blocking launch in background
        cmd = [str(target_exe), *validated_args]

        # Use asyncio / subprocess without shell=True to guarantee argument isolation
        def _launch() -> int | None:
            creationflags = 0
            if os.name == "nt":
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

            proc = subprocess.Popen(
                cmd,
                creationflags=creationflags,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return proc.pid

        pid = await asyncio.to_thread(_launch)

        return SkillResult(
            success=True,
            data={
                "launched": True,
                "app_name": app_name,
                "executable_path": str(target_exe),
                "arguments": validated_args,
                "pid": pid,
            },
        )
