import logging

from backend.app.core.logging import (
    SENSITIVE_QUERY_REGEX,
    QueryScrubFilter,
    scrub_sensitive_query_strings,
)


def test_sensitive_query_regex() -> None:
    raw_url = "http://127.0.0.1:8000/ws?token=my_secret_token_123&other=safe"
    scrubbed = SENSITIVE_QUERY_REGEX.sub(r"\1[REDACTED]", raw_url)
    assert scrubbed == "http://127.0.0.1:8000/ws?token=[REDACTED]&other=safe"

    raw_setup = "http://127.0.0.1:8000/setup?setup_token=topsecret456"
    assert (
        SENSITIVE_QUERY_REGEX.sub(r"\1[REDACTED]", raw_setup)
        == "http://127.0.0.1:8000/setup?setup_token=[REDACTED]"
    )


def test_structlog_processor_scrubs_event_dict() -> None:
    event_dict = {
        "event": "GET /ws?token=secret_abc123",
        "url": "http://localhost:8000/api?api_key=sk-12345&mode=test",
        "nested": {"path": "/auth?access_token=jwt_xyz_999"},
        "safe_key": "safe_value",
    }
    processed = scrub_sensitive_query_strings(None, "info", event_dict)

    assert processed["event"] == "GET /ws?token=[REDACTED]"
    assert processed["url"] == "http://localhost:8000/api?api_key=[REDACTED]&mode=test"
    assert processed["nested"]["path"] == "/auth?access_token=[REDACTED]"
    assert processed["safe_key"] == "safe_value"


def test_query_scrub_filter_logging() -> None:
    filter_instance = QueryScrubFilter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Request received: %s",
        args=("http://localhost:8000/ws?token=jwt_sensitive_key",),
        exc_info=None,
    )
    filter_instance.filter(record)
    assert isinstance(record.args, tuple)
    first_arg = record.args[0]
    assert isinstance(first_arg, str)
    assert "[REDACTED]" in first_arg
    assert "jwt_sensitive_key" not in first_arg
