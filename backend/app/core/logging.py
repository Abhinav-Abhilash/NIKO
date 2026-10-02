import logging
import re
import sys
import threading
from contextvars import ContextVar
from typing import Any, cast

import structlog

# Context variable for request-scoped correlation ID
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")

# Sensitive query params
SENSITIVE_QUERY_REGEX = re.compile(
    r"([?&](?:token|setup_token|api_key|key|secret|password|access_token|refresh_token)=)[^&\s]*",
    re.IGNORECASE,
)

# Known provider key patterns
GEMINI_KEY_REGEX = re.compile(r"\bAIza[0-9A-Za-z\-_]{20,}\b")
GROQ_KEY_REGEX = re.compile(r"\bgsk_[a-zA-Z0-9]{20,}\b")
OPENROUTER_KEY_REGEX = re.compile(r"\bsk-or-(?:v1-)?[a-zA-Z0-9_\-]{20,}\b")
GENERIC_SK_REGEX = re.compile(r"\bsk-[a-zA-Z0-9_\-]{20,}\b")
BEARER_AUTH_REGEX = re.compile(r"\bBearer\s+[a-zA-Z0-9_\-\.]{16,}\b", re.IGNORECASE)
HEADER_KEY_REGEX = re.compile(r"(?i)\b(x-goog-api-key|api[-_]?key):\s*([a-zA-Z0-9_\-\.]{8,})")

SENSITIVE_FIELD_NAMES = re.compile(
    r"(?i)(^key$|api[_-]?key|secret|password|auth|credential|gemini.*key|groq.*key|openrouter.*key|token)"
)


_SENSITIVE_TOKENS: set[str] = set()
_LOCK = threading.Lock()


def register_sensitive_token(token: str | None) -> None:
    """Register a token or key that must be redacted from all structlog and uvicorn logs."""
    if not token or len(token.strip()) < 6:
        return
    with _LOCK:
        _SENSITIVE_TOKENS.add(token.strip())


def redact_string(val: str) -> str:
    """Redact all sensitive keys, tokens, and query parameters from a string."""
    if not val:
        return val

    # 1. Scrub registered tokens
    with _LOCK:
        tokens = list(_SENSITIVE_TOKENS)
    for tok in tokens:
        if tok in val:
            val = val.replace(tok, "[REDACTED]")

    # 2. Scrub regex patterns
    val = SENSITIVE_QUERY_REGEX.sub(r"\1[REDACTED]", val)
    val = GEMINI_KEY_REGEX.sub("[REDACTED]", val)
    val = GROQ_KEY_REGEX.sub("[REDACTED]", val)
    val = OPENROUTER_KEY_REGEX.sub("[REDACTED]", val)
    val = GENERIC_SK_REGEX.sub("[REDACTED]", val)
    val = BEARER_AUTH_REGEX.sub("Bearer [REDACTED]", val)
    val = HEADER_KEY_REGEX.sub(r"\1: [REDACTED]", val)

    return val


def redact_sensitive_data(
    _: Any, __: str, event_dict: structlog.types.EventDict
) -> structlog.types.EventDict:
    """Recursively redact sensitive keys, tokens, and query strings from log event dicts."""

    def _scrub(k: Any, val: Any) -> Any:
        if isinstance(k, str) and SENSITIVE_FIELD_NAMES.search(k):
            return "[REDACTED]"
        if isinstance(val, str):
            return redact_string(val)
        if isinstance(val, dict):
            return {k2: _scrub(k2, v2) for k2, v2 in val.items()}
        if isinstance(val, list):
            return [_scrub(None, item) for item in val]
        return val

    return {k: _scrub(k, v) for k, v in event_dict.items()}


# Backward compatibility alias
scrub_sensitive_query_strings = redact_sensitive_data


class RedactionFilter(logging.Filter):
    """Standard logging filter scrubbing sensitive keys and query parameters from records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_string(record.msg)
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(
                    redact_string(a) if isinstance(a, str) else a
                    for a in record.args
                )
            elif isinstance(record.args, dict):
                record.args = {
                    k: (redact_string(v) if isinstance(v, str) else v)
                    for k, v in record.args.items()
                }
        return True


# Backward compatibility alias
QueryScrubFilter = RedactionFilter


def add_request_id(_: Any, __: str, event_dict: structlog.types.EventDict) -> structlog.types.EventDict:
    req_id = request_id_ctx.get()
    if req_id:
        event_dict["request_id"] = req_id
    return event_dict


def setup_logging(log_level: str = "INFO", app_env: str = "development") -> None:
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        add_request_id,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        redact_sensitive_data,
    ]

    if app_env == "production":
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    redaction_filter = RedactionFilter()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(redaction_filter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    root_logger.addFilter(redaction_filter)

    # Attach filter and configure uvicorn loggers
    for uvicorn_name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        uv_log = logging.getLogger(uvicorn_name)
        uv_log.addFilter(redaction_filter)
        for h in uv_log.handlers:
            h.addFilter(redaction_filter)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)



def get_logger(name: str = "niko") -> structlog.stdlib.BoundLogger:
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))
