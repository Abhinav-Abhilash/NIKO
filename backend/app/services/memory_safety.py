import re

from backend.app.core.logging import (
    BEARER_AUTH_REGEX,
    GEMINI_KEY_REGEX,
    GENERIC_SK_REGEX,
    GROQ_KEY_REGEX,
    OPENROUTER_KEY_REGEX,
)

# Additional secret patterns: Private keys, JWTs, Fernet keys, password declarations
PRIVATE_KEY_REGEX = re.compile(r"-----BEGIN\s+[A-Z0-9_-]*\s*PRIVATE\s+KEY-----", re.IGNORECASE)
JWT_REGEX = re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")
FERNET_KEY_REGEX = re.compile(r"\b[A-Za-z0-9_-]{43}=\b")
PASSWORD_DECLARATION_REGEX = re.compile(
    r"(?i)\b(?:password|passwd|api_secret|client_secret)\s*[:=]\s*['\"]?([^\s'\"]{6,})['\"]?"
)

# Minor extra layer: overt prompt injection phrases
INJECTION_PHRASE_REGEX = re.compile(
    r"(?i)\b("
    r"(?:ignore|disregard)\s+(?:all\s+|earlier\s+|previous\s+|prior\s+)?(?:system\s+)?instructions|"
    r"you\s+are\s+now\s+(?:in\s+)?developer\s+mode|"
    r"(?:system\s+)?override\s*[:\s]+|"
    r"override\s+(?:the\s+)?system\s+prompt|"
    r"disregard\s+(?:all\s+)?safety\s+guidelines|"
    r"system\s*:\s*you\s+must|"
    r"<\|im_start\|>system"
    r")\b"
)

MEMORY_TAG_OPEN = "<user_memory>"
MEMORY_TAG_CLOSE = "</user_memory>"


def contains_secrets(text: str) -> tuple[bool, str | None]:
    """
    Scans memory content against known API key, JWT, private key, and credential patterns.
    Returns (True, reason) if any secret pattern matches.
    """
    if not text:
        return False, None

    if GEMINI_KEY_REGEX.search(text):
        return True, "Detected Google Gemini API key. Credentials cannot be stored in long-term memory."
    if GROQ_KEY_REGEX.search(text):
        return True, "Detected Groq API key. Credentials cannot be stored in long-term memory."
    if OPENROUTER_KEY_REGEX.search(text) or GENERIC_SK_REGEX.search(text):
        return True, "Detected API key token. Credentials cannot be stored in long-term memory."
    if BEARER_AUTH_REGEX.search(text):
        return True, "Detected Bearer authentication token. Credentials cannot be stored in long-term memory."
    if PRIVATE_KEY_REGEX.search(text):
        return True, "Detected cryptographic private key block. Secrets cannot be stored in long-term memory."
    if JWT_REGEX.search(text):
        return True, "Detected JSON Web Token (JWT). Credentials cannot be stored in long-term memory."
    if FERNET_KEY_REGEX.search(text):
        return True, "Detected symmetric Fernet encryption key. Secrets cannot be stored in long-term memory."
    if PASSWORD_DECLARATION_REGEX.search(text):
        return True, "Detected plaintext password declaration. Passwords cannot be stored in long-term memory."

    return False, None


def contains_injection_phrases(text: str) -> tuple[bool, str | None]:
    """
    Minor safety layer detecting overt prompt injection / instruction hijacking patterns.
    """
    if not text:
        return False, None

    match = INJECTION_PHRASE_REGEX.search(text)
    if match:
        return True, f"Detected potential prompt injection pattern: '{match.group(0)}'."

    return False, None


def escape_memory_tags(text: str) -> str:
    """
    Escapes opening and closing memory tags inside memory content to prevent delimiter escaping.
    Memories are data, not instructions.
    """
    if not text:
        return ""
    escaped = text.replace("</user_memory>", "&lt;/user_memory&gt;")
    escaped = escaped.replace("<user_memory>", "&lt;user_memory&gt;")
    escaped = escaped.replace("<user_memory ", "&lt;user_memory ")
    return escaped


def wrap_user_memory(content: str, key: str | None = None, category: str = "general") -> str:
    """
    Wraps sanitized memory in a single containment tag:
    <user_memory key="..." category="...">safe_content</user_memory>
    """
    safe_content = escape_memory_tags(content.strip())
    attr_parts = []
    if key:
        clean_key = key.replace('"', "").strip()
        attr_parts.append(f'key="{clean_key}"')
    if category:
        clean_cat = category.replace('"', "").strip()
        attr_parts.append(f'category="{clean_cat}"')

    attrs_str = (" " + " ".join(attr_parts)) if attr_parts else ""
    return f"<user_memory{attrs_str}>\n{safe_content}\n</user_memory>"
