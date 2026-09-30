import asyncio
import sys
from typing import Any

from backend.app.core.exceptions import ValidationFailedError
from backend.app.core.logging import get_logger
from backend.app.skills.base import BaseSkill, SkillContext, SkillManifest, SkillResult

logger = get_logger("volume_brightness_skill")


class VolumeBrightnessSkill(BaseSkill):
    """Controls Windows system audio volume, mute state, and display brightness."""

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="volume_brightness",
            description=(
                "Query or adjust system audio master volume, mute states, and monitor display brightness."
            ),
            default_tier="CONFIRM",
            default_autonomy="auto+log",
            timeout_seconds=10,
            parameters_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "get_volume",
                            "set_volume",
                            "mute_volume",
                            "unmute_volume",
                            "get_brightness",
                            "set_brightness",
                        ],
                        "description": "Operation to perform on system audio or display brightness.",
                    },
                    "level": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 100,
                        "description": "Target percentage level (0-100) for set_volume or set_brightness.",
                    },
                    "display_index": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "Index of display monitor for brightness adjustments (default 0).",
                        "default": 0,
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        )

    async def execute(self, arguments: dict[str, Any], _context: SkillContext) -> SkillResult:
        action = arguments.get("action")
        if not action:
            raise ValidationFailedError("Parameter 'action' is required.")

        level = arguments.get("level")
        display_index = int(arguments.get("display_index") or 0)

        if action in ("set_volume", "set_brightness") and (
            level is None or not (0 <= int(level) <= 100)
        ):
            raise ValidationFailedError(f"Action '{action}' requires a valid 'level' between 0 and 100.")

        res = await asyncio.to_thread(self._handle_action_sync, action, level, display_index)
        if "error" in res:
            return SkillResult(success=False, error=res["error"])

        return SkillResult(success=True, data=res)

    def _handle_action_sync(self, action: str, level: int | None, display_index: int) -> dict[str, Any]:
        if sys.platform != "win32":
            return {"error": "Volume and brightness controls are only available on Windows host environments."}

        if action in ("get_volume", "set_volume", "mute_volume", "unmute_volume"):
            return self._handle_audio(action, level)
        elif action in ("get_brightness", "set_brightness"):
            return self._handle_brightness(action, level, display_index)
        else:
            return {"error": f"Unknown action: '{action}'"}

    def _handle_audio(self, action: str, level: int | None) -> dict[str, Any]:
        try:
            import comtypes
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

            # Initialize COM for current worker thread
            comtypes.CoInitialize()
            try:
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None)
                volume = interface.QueryInterface(IAudioEndpointVolume)

                if action == "get_volume":
                    current_scalar = volume.GetMasterVolumeLevelScalar()
                    current_mute = bool(volume.GetMute())
                    return {
                        "action": "get_volume",
                        "volume_level": int(round(current_scalar * 100)),
                        "is_muted": current_mute,
                    }

                elif action == "set_volume":
                    target_scalar = float(level) / 100.0  # type: ignore[arg-type]
                    volume.SetMasterVolumeLevelScalar(target_scalar, None)
                    return {
                        "action": "set_volume",
                        "volume_level": level,
                        "is_muted": bool(volume.GetMute()),
                    }

                elif action == "mute_volume":
                    volume.SetMute(1, None)
                    return {
                        "action": "mute_volume",
                        "is_muted": True,
                        "volume_level": int(round(volume.GetMasterVolumeLevelScalar() * 100)),
                    }

                elif action == "unmute_volume":
                    volume.SetMute(0, None)
                    return {
                        "action": "unmute_volume",
                        "is_muted": False,
                        "volume_level": int(round(volume.GetMasterVolumeLevelScalar() * 100)),
                    }
            finally:
                comtypes.CoUninitialize()

        except Exception as exc:
            logger.warning("Audio control operation encountered an error", action=action, error=str(exc))
            return {"error": f"Audio operation '{action}' failed: {exc}"}

        return {"error": "Audio operation completed without return state."}

    def _handle_brightness(self, action: str, level: int | None, display_index: int) -> dict[str, Any]:
        try:
            import screen_brightness_control as sbc

            if action == "get_brightness":
                brightness_list = sbc.get_brightness(display=display_index)
                current = brightness_list[0] if isinstance(brightness_list, list) and brightness_list else brightness_list
                return {
                    "action": "get_brightness",
                    "brightness_level": current,
                    "display_index": display_index,
                }

            elif action == "set_brightness":
                sbc.set_brightness(level, display=display_index)
                return {
                    "action": "set_brightness",
                    "brightness_level": level,
                    "display_index": display_index,
                }

        except Exception as exc:
            logger.warning("Display brightness operation encountered an error", action=action, error=str(exc))
            return {"error": f"Brightness operation '{action}' failed: {exc}"}

        return {"error": "Brightness operation completed without return state."}
