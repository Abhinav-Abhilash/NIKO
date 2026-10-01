import ctypes
import logging
from typing import Any

from backend.app.skills.base import BaseSkill, SkillContext, SkillManifest, SkillResult

logger = logging.getLogger(__name__)

SW_MINIMIZE = 6
SW_RESTORE = 9
WM_CLOSE = 0x0010


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class POINT(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_long),
        ("y", ctypes.c_long),
    ]


def get_window_rect(hwnd: Any) -> dict[str, int] | None:
    """Get pixel bounds for a given window handle."""
    user32 = ctypes.windll.user32
    rect = RECT()
    if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return {
            "left": rect.left,
            "top": rect.top,
            "right": rect.right,
            "bottom": rect.bottom,
            "width": rect.right - rect.left,
            "height": rect.bottom - rect.top,
        }
    return None


def list_visible_windows(include_rects: bool = False) -> list[dict[str, Any]]:
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
                    entry: dict[str, Any] = {"hwnd": hwnd, "title": title}
                    if include_rects:
                        entry["rect"] = get_window_rect(hwnd)
                    results.append(entry)
        return True

    cb = WNDENUMPROC(enum_windows_callback)
    user32.EnumWindows(cb, 0)
    return results


def find_window_by_title_query(query: str, include_rect: bool = False) -> dict[str, Any] | None:
    """Find the best matching visible window whose title contains query (case-insensitive)."""
    clean_q = query.strip().lower()
    windows = list_visible_windows(include_rects=include_rect)
    for w in windows:
        if clean_q in w["title"].lower():
            return w
    return None


def get_desktop_environment_state() -> dict[str, Any]:
    """Capture real-time desktop state: active foreground window, cursor coordinates, and visible windows."""
    user32 = ctypes.windll.user32

    # Active Foreground Window
    active_hwnd = user32.GetForegroundWindow()
    active_title = ""
    active_rect = None
    if active_hwnd:
        length = user32.GetWindowTextLengthW(active_hwnd)
        if length > 0:
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(active_hwnd, buff, length + 1)
            active_title = buff.value.strip()
        active_rect = get_window_rect(active_hwnd)

    # Mouse cursor coordinates
    cursor_pos = POINT()
    cursor_dict = {"x": 0, "y": 0}
    if user32.GetCursorPos(ctypes.byref(cursor_pos)):
        cursor_dict = {"x": cursor_pos.x, "y": cursor_pos.y}

    visible = list_visible_windows(include_rects=True)

    return {
        "active_window": {
            "title": active_title,
            "rect": active_rect,
        },
        "cursor": cursor_dict,
        "visible_windows": [{"title": w["title"], "rect": w.get("rect")} for w in visible],
        "count": len(visible),
    }


class WindowControlSkill(BaseSkill):
    """
    Skill for inspecting, enumerating, focusing, minimizing, and closing open desktop windows on Windows.
    Closing windows requires CONFIRM tier to prevent unsaved work loss.
    """

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="window_control",
            description="Inspect desktop environment, list, focus, minimize, or close open application windows on Windows.",
            default_tier="CONFIRM",
            default_autonomy="ask",
            timeout_seconds=5,
            parameters_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["inspect", "list", "focus", "minimize", "close"],
                        "description": "Action to perform: 'inspect' returns active window + cursor + desktop bounds, 'list' returns open windows, 'focus' brings window to front, 'minimize' hides window, 'close' closes window.",
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
        if action not in ("inspect", "list", "focus", "minimize", "close"):
            return SkillResult(
                success=False,
                error=f"Unsupported window action: '{action}'",
            )

        title_query = arguments.get("title_query") or arguments.get("title") or ""
        user32 = ctypes.windll.user32

        if action == "inspect":
            env = get_desktop_environment_state()
            return SkillResult(
                success=True,
                data=env,
            )

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
