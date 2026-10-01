import ctypes
import logging
from typing import Any

from backend.app.skills.base import BaseSkill, SkillContext, SkillManifest, SkillResult

logger = logging.getLogger(__name__)

VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_PLAY_PAUSE = 0xB3
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF

KEYEVENTF_KEYUP = 0x0002


def send_virtual_key(vk_code: int) -> None:
    """Send a virtual key down and up event via Win32 user32 keybd_event."""
    user32 = ctypes.windll.user32
    user32.keybd_event(vk_code, 0, 0, 0)
    user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)


class MediaControlSkill(BaseSkill):
    """
    Skill for controlling media playback (play/pause, next, prev, volume up/down, mute).
    Uses native Windows virtual key signals.
    """

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="media_control",
            description="Control media playback and audio volume on Windows (play/pause, next track, previous track, mute, volume up, volume down).",
            default_tier="SAFE",
            default_autonomy="auto",
            timeout_seconds=5,
            parameters_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["play_pause", "next", "previous", "mute", "volume_up", "volume_down"],
                        "description": "Media command to execute.",
                    },
                    "repeat": {
                        "type": "integer",
                        "description": "Optional repeat count for volume adjustments (1 to 10). Default is 1.",
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        )

    async def execute(self, arguments: dict[str, Any], _context: SkillContext) -> SkillResult:
        action = arguments.get("action", "")
        repeat = max(1, min(10, int(arguments.get("repeat", 1))))

        key_map = {
            "play_pause": VK_MEDIA_PLAY_PAUSE,
            "next": VK_MEDIA_NEXT_TRACK,
            "previous": VK_MEDIA_PREV_TRACK,
            "mute": VK_VOLUME_MUTE,
            "volume_up": VK_VOLUME_UP,
            "volume_down": VK_VOLUME_DOWN,
        }

        vk_code = key_map.get(action)
        if not vk_code:
            return SkillResult(
                success=False,
                error=f"Unsupported media action '{action}'. Valid: {list(key_map.keys())}",
            )

        try:
            for _ in range(repeat):
                send_virtual_key(vk_code)

            return SkillResult(
                success=True,
                data={"action": action, "repeat": repeat},
            )

        except Exception as e:
            logger.error("Failed to execute media control virtual key: %s", e)
            return SkillResult(
                success=False,
                error=f"Media control action failed: {e}",
            )
