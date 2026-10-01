import ctypes
import logging
from typing import Any

from backend.app.skills.base import BaseSkill, SkillContext, SkillManifest, SkillResult

logger = logging.getLogger(__name__)

SW_MINIMIZE = 6
SW_RESTORE = 9
WM_CLOSE = 0x0010


def list_visible_windows() -> list[dict[str, Any]]:
    """Enumerate all open, visible Windows top-level windows with title bar text."""
    user32 = ctypes.windll.user32
    results: list[dict[str, Any]] = []

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def enum_windows_callback(hwnd: Any, _: Any) -> bool:
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                title = buff.value.strip()
                if title and title not in ("Program Manager", "NIKO Overlay"):
                    results.append({"hwnd": hwnd, "title": title})
        return True

    cb = WNDENUMPROC(enum_windows_callback)
    user32.EnumWindows(cb, 0)
    return results


def find_window_by_title_query(query: str) -> dict[str, Any] | None:
    """Find the best matching visible window whose title contains query (case-insensitive)."""
    clean_q = query.strip().lower()
    windows = list_visible_windows()
    for w in windows:
        if clean_q in w["title"].lower():
            return w
    return None


class WindowControlSkill(BaseSkill):
    """
    Skill for enumerating, focusing, minimizing, and closing open desktop windows on Windows.
    Closing windows requires CONFIRM tier to prevent unsaved work loss.
    """

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="window_control",
            description="List, focus, minimize, or close open application windows on Windows.",
            default_tier="CONFIRM",
            default_autonomy="ask",
            timeout_seconds=5,
            parameters_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "focus", "minimize", "close"],
                        "description": "Action to perform: 'list' returns open windows, 'focus' brings window to front, 'minimize' hides window, 'close' closes window.",
                    },
                    "title_query": {
                        "type": "string",
                        "description": "Window title substring to search for (e.g. 'Notepad', 'Chrome', 'Visual Studio').",
                    },
                    "title": {
                        "type": "string",
                        "description": "Alias for title_query.",
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        )

    async def execute(self, arguments: dict[str, Any], _context: SkillContext) -> SkillResult:
        action = arguments.get("action", "list")
        if action not in ("list", "focus", "minimize", "close"):
            return SkillResult(
                success=False,
                error=f"Unsupported window action: '{action}'",
            )

        title_query = arguments.get("title_query") or arguments.get("title") or ""

        user32 = ctypes.windll.user32

        if action == "list":
            windows = list_visible_windows()
            return SkillResult(
                success=True,
                data={"windows": [w["title"] for w in windows], "count": len(windows)},
            )

        if not title_query.strip():
            return SkillResult(
                success=False,
                error="Argument 'title_query' or 'title' is required for focus, minimize, and close actions.",
            )


        match = find_window_by_title_query(title_query)
        if not match:
            return SkillResult(
                success=False,
                error=f"No active window matching '{title_query}' was found.",
            )

        hwnd = match["hwnd"]
        matched_title = match["title"]

        try:
            if action == "focus":
                user32.ShowWindow(hwnd, SW_RESTORE)
                user32.SetForegroundWindow(hwnd)
                return SkillResult(
                    success=True,
                    data={"action": "focus", "title": matched_title},
                )

            elif action == "minimize":
                user32.ShowWindow(hwnd, SW_MINIMIZE)
                return SkillResult(
                    success=True,
                    data={"action": "minimize", "title": matched_title},
                )

            elif action == "close":
                user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
                return SkillResult(
                    success=True,
                    data={"action": "close", "title": matched_title},
                )


            else:
                return SkillResult(
                    success=False,
                    error=f"Unsupported window action '{action}'.",
                )
        except Exception as e:
            logger.error("Window control action failed: %s", e)
            return SkillResult(
                success=False,
                error=f"Window control operation failed: {e}",
            )
