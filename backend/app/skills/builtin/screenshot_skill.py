import asyncio
import base64
import io
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.app.core.logging import get_logger
from backend.app.skills.base import BaseSkill, SkillContext, SkillManifest, SkillResult

logger = get_logger("screenshot_skill")

SCREENSHOTS_DIR = Path("storage/screenshots")


class ScreenshotSkill(BaseSkill):
    """Captures desktop screenshots across single or multiple monitors on Windows."""

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="screenshot",
            description="Capture a screenshot of primary or secondary monitors and save locally.",
            default_tier="SAFE",
            default_autonomy="auto",
            timeout_seconds=15,
            parameters_schema={
                "type": "object",
                "properties": {
                    "monitor_index": {
                        "type": "integer",
                        "description": (
                            "Monitor to capture (1 = primary display, 0 = all displays merged, "
                            "2+ = secondary display). Default is 1."
                        ),
                        "default": 1,
                        "minimum": 0,
                    },
                    "save_to_disk": {
                        "type": "boolean",
                        "description": "Whether to save the full-resolution screenshot to storage (default true).",
                        "default": True,
                    },
                    "include_thumbnail_base64": {
                        "type": "boolean",
                        "description": "Whether to generate a lightweight Base64 JPEG thumbnail (default false).",
                        "default": False,
                    },
                },
                "additionalProperties": False,
            },
        )

    async def execute(self, arguments: dict[str, Any], _context: SkillContext) -> SkillResult:
        monitor_idx = int(arguments.get("monitor_index") if arguments.get("monitor_index") is not None else 1)
        save_to_disk = bool(arguments.get("save_to_disk") if arguments.get("save_to_disk") is not None else True)
        include_thumbnail = bool(arguments.get("include_thumbnail_base64") or False)

        def _capture() -> dict[str, Any]:
            try:
                import mss
                from PIL import Image
            except ImportError as err:
                return {"error": f"Required screenshot libraries (mss/pillow) not available: {err}"}

            SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
            timestamp_str = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            unique_id = uuid.uuid4().hex[:8]
            filename = f"screenshot_{timestamp_str}_{unique_id}.png"
            file_path = SCREENSHOTS_DIR / filename

            with mss.mss() as sct:
                monitors = sct.monitors
                if monitor_idx >= len(monitors):
                    target_idx = 1 if len(monitors) > 1 else 0
                else:
                    target_idx = monitor_idx

                target_monitor = monitors[target_idx]
                sct_img = sct.grab(target_monitor)

                # Convert raw BGRA bytes to PIL Image (RGB)
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

                width, height = img.size
                saved_path_str: str | None = None

                if save_to_disk:
                    img.save(str(file_path), format="PNG", optimize=True)
                    saved_path_str = str(file_path.resolve())

                thumbnail_b64: str | None = None
                if include_thumbnail:
                    thumb = img.copy()
                    thumb.thumbnail((320, 320))
                    buffer = io.BytesIO()
                    thumb.save(buffer, format="JPEG", quality=75)
                    thumbnail_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

                return {
                    "success": True,
                    "monitor_index": target_idx,
                    "width": width,
                    "height": height,
                    "file_path": saved_path_str,
                    "file_name": filename if saved_path_str else None,
                    "captured_at": datetime.now(UTC).isoformat(),
                    "thumbnail_base64": thumbnail_b64,
                }

        res = await asyncio.to_thread(_capture)

        if "error" in res:
            return SkillResult(success=False, error=res["error"])

        return SkillResult(success=True, data=res)
