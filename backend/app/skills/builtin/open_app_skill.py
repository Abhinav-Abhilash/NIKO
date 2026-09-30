import asyncio
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from backend.app.core.exceptions import ValidationFailedError
from backend.app.core.security import (
    DEFAULT_APP_ALLOWLIST,
    validate_open_app_path,
)
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
        app_name = (arguments.get("app_name") or "").strip().lower()
        executable_path = (arguments.get("executable_path") or "").strip()
        raw_args = arguments.get("arguments") or []

        if not isinstance(raw_args, list) or not all(isinstance(a, str) for a in raw_args):
            raise ValidationFailedError("Arguments parameter must be a list of strings.")

        target_exe: Path | None = None

        if executable_path:
            target_exe = validate_open_app_path(executable_path)
        elif app_name:
            # Check default allowlist alias
            if app_name in DEFAULT_APP_ALLOWLIST:
                target_exe = validate_open_app_path(DEFAULT_APP_ALLOWLIST[app_name])
            else:
                # Attempt to resolve via PATH and validate
                resolved = shutil.which(app_name)
                if resolved:
                    target_exe = validate_open_app_path(resolved)
                else:
                    raise ValidationFailedError(
                        f"Application '{app_name}' was not found in allowlist or system PATH."
                    )
        else:
            raise ValidationFailedError("Either 'app_name' or 'executable_path' must be provided.")

        if not target_exe.exists():
            raise ValidationFailedError(f"Target executable does not exist: {target_exe}")

        # Non-blocking launch in background
        cmd = [str(target_exe), *raw_args]

        # Use asyncio / subprocess without shell=True to guarantee argument isolation
        def _launch() -> int | None:
            # On Windows, DETACHED_PROCESS / CREATE_NEW_PROCESS_GROUP can be used if available
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
                "app_name": app_name or target_exe.stem,
                "executable_path": str(target_exe),
                "arguments": raw_args,
                "pid": pid,
            },
        )
