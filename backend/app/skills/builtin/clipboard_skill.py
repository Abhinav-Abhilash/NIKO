import ctypes
import logging
from typing import Any

from backend.app.skills.base import BaseSkill, SkillContext, SkillManifest, SkillResult

logger = logging.getLogger(__name__)

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
GMEM_ZEROINIT = 0x0040


def get_clipboard_text() -> str:
    """Safely retrieve text from Windows clipboard via ctypes user32."""
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        user32.OpenClipboard.argtypes = [ctypes.c_void_p]
        user32.OpenClipboard.restype = ctypes.c_bool
        user32.GetClipboardData.argtypes = [ctypes.c_uint]
        user32.GetClipboardData.restype = ctypes.c_void_p
        user32.CloseClipboard.restype = ctypes.c_bool

        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalUnlock.restype = ctypes.c_bool

        if not user32.OpenClipboard(None):
            return ""

        try:
            handle = user32.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                return ""

            pointer = kernel32.GlobalLock(handle)
            if not pointer:
                return ""

            try:
                text = ctypes.wstring_at(pointer)
                return text
            finally:
                kernel32.GlobalUnlock(handle)
        finally:
            user32.CloseClipboard()
    except Exception as e:
        logger.warning("Could not read clipboard via ctypes: %s", e)
        return ""


def set_clipboard_text(text: str) -> bool:
    """Safely write text to Windows clipboard via ctypes user32."""
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        user32.OpenClipboard.argtypes = [ctypes.c_void_p]
        user32.OpenClipboard.restype = ctypes.c_bool
        user32.EmptyClipboard.restype = ctypes.c_bool
        user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
        user32.SetClipboardData.restype = ctypes.c_void_p
        user32.CloseClipboard.restype = ctypes.c_bool

        kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
        kernel32.GlobalAlloc.restype = ctypes.c_void_p
        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalUnlock.restype = ctypes.c_bool

        if not user32.OpenClipboard(None):
            return False

        try:
            user32.EmptyClipboard()
            encoded = text.encode("utf-16-le") + b"\x00\x00"
            h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT, len(encoded))
            if not h_mem:
                return False

            pointer = kernel32.GlobalLock(h_mem)
            if not pointer:
                return False

            try:
                ctypes.memmove(pointer, encoded, len(encoded))
            finally:
                kernel32.GlobalUnlock(h_mem)

            user32.SetClipboardData(CF_UNICODETEXT, h_mem)
            return True
        finally:
            user32.CloseClipboard()
    except Exception as e:
        logger.warning("Could not write clipboard via ctypes: %s", e)
        return False


class ClipboardSkill(BaseSkill):
    """
    Skill for reading from and writing to the system clipboard.
    Read actions require CONFIRM tier (to protect clipboard passwords).
    Write actions are SAFE tier.
    """

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="clipboard",
            description="Read text from or write text to the system clipboard. Reading requires user confirmation.",
            default_tier="CONFIRM",
            default_autonomy="ask",
            timeout_seconds=5,
            parameters_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["read", "write"],
                        "description": "Action to perform: 'read' retrieves clipboard text, 'write' places text into clipboard.",
                    },
                    "text": {
                        "type": "string",
                        "description": "Text to place into the clipboard when action is 'write'.",
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        )

    async def execute(self, arguments: dict[str, Any], _context: SkillContext) -> SkillResult:
        action = arguments.get("action", "read")

        if action == "read":
            content = get_clipboard_text()
            if not content:
                return SkillResult(
                    success=True,
                    data={"action": "read", "content": "", "empty": True},
                    message="Clipboard is empty or contains non-text data.",
                )
            return SkillResult(
                success=True,
                data={
                    "action": "read",
                    "content": content,
                    "length": len(content),
                },
                message=f"Successfully read {len(content)} characters from clipboard.",
            )

        elif action == "write":
            text_to_write = arguments.get("text", "")
            if not text_to_write:
                return SkillResult(
                    success=False,
                    error="Argument 'text' is required when action is 'write'.",
                )

            ok = set_clipboard_text(text_to_write)
            if ok:
                return SkillResult(
                    success=True,
                    data={"action": "write", "length": len(text_to_write)},
                    message=f"Copied {len(text_to_write)} characters to clipboard.",
                )

            return SkillResult(
                success=False,
                error="Failed to open or write to host clipboard.",
            )

        else:
            return SkillResult(
                success=False,
                error=f"Unsupported clipboard action '{action}'. Use 'read' or 'write'.",
            )
