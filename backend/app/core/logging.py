import logging
import re
import sys
from contextvars import ContextVar
from typing import Any, cast

import structlog

# Context variable for request-scoped correlation ID
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")

SENSITIVE_QUERY_REGEX = re.compile(
    r"([?&](?:token|setup_token|api_key|secret|password|access_token|refresh_token)=)[^&\s]*",
    re.IGNORECASE,
)


def scrub_sensitive_query_strings(
    _: Any, __: str, event_dict: structlog.types.EventDict
) -> structlog.types.EventDict:
    """Recursively scrub sensitive query string parameters (?token=...) from log event dicts."""

    def _scrub(val: Any) -> Any:
        if isinstance(val, str):
            return SENSITIVE_QUERY_REGEX.sub(r"\1[REDACTED]", val)
        if isinstance(val, dict):
            return {k: _scrub(v) for k, v in val.items()}
        if isinstance(val, list):
            return [_scrub(v) for v in val]
        return val

    return {k: _scrub(v) for k, v in event_dict.items()}


class QueryScrubFilter(logging.Filter):
    """Standard logging filter scrubbing sensitive query parameters from records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = SENSITIVE_QUERY_REGEX.sub(r"\1[REDACTED]", record.msg)
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(
                    SENSITIVE_QUERY_REGEX.sub(r"\1[REDACTED]", a) if isinstance(a, str) else a
                    for a in record.args
                )
            elif isinstance(record.args, dict):
                record.args = {
                    k: (
                        SENSITIVE_QUERY_REGEX.sub(r"\1[REDACTED]", v)
                        if isinstance(v, str)
                        else v
                    )
                    for k, v in record.args.items()
                }
        return True


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
        scrub_sensitive_query_strings,
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

    scrub_filter = QueryScrubFilter()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(scrub_filter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    root_logger.addFilter(scrub_filter)

    # Attach filter and configure uvicorn loggers
    uvicorn_logger = logging.getLogger("uvicorn.access")
    uvicorn_logger.addFilter(scrub_filter)
    uvicorn_logger.setLevel(logging.WARNING)

    logging.getLogger("aiosqlite").setLevel(logging.WARNING)


def get_logger(name: str = "niko") -> structlog.stdlib.BoundLogger:
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))
