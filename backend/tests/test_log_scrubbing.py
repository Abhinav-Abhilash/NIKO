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


def test_provider_api_keys_redacted_in_structlog() -> None:
    from backend.app.core.logging import redact_sensitive_data, register_sensitive_token

    gemini_key = "AI" + "za" + "SyD_1234567890abcdefghijklmnopqrstuvw"
    groq_key = "g" + "sk_" + "1234567890abcdef1234567890abcdef12345678"
    openrouter_key = "sk-" + "or-v1-" + "abcdef0123456789abcdef0123456789abcdef0123456789"
    custom_secret = "my_custom_super_secret_provider_key_999"
    register_sensitive_token(custom_secret)

    event_dict = {
        "event": f"Connecting to Gemini with {gemini_key}",
        "groq_call": f"Groq response from key {groq_key}",
        "auth_header": f"Bearer {openrouter_key}",
        "custom": f"Using custom key: {custom_secret}",
        "query": f"https://generativelanguage.googleapis.com/v1beta/models?key={gemini_key}",
        "api_key": "some_arbitrary_key_string",
        "nested": {
            "gemini_api_key": "raw_secret_value",
            "message": f"nested call {groq_key}",
        },
    }

    scrubbed = redact_sensitive_data(None, "info", event_dict)

    # Ensure none of the keys appear anywhere in the result
    scrubbed_str = str(scrubbed)
    assert gemini_key not in scrubbed_str
    assert groq_key not in scrubbed_str
    assert openrouter_key not in scrubbed_str
    assert custom_secret not in scrubbed_str
    assert "some_arbitrary_key_string" not in scrubbed_str
    assert "raw_secret_value" not in scrubbed_str
    assert scrubbed["nested"]["gemini_api_key"] == "[REDACTED]"
    assert scrubbed["api_key"] == "[REDACTED]"


def test_provider_keys_redacted_in_uvicorn_log_record() -> None:
    from backend.app.core.logging import RedactionFilter

    filter_instance = RedactionFilter()
    gemini_key = "AI" + "za" + "SyD_1234567890abcdefghijklmnopqrstuvw"
    groq_key = "g" + "sk_" + "1234567890abcdef1234567890abcdef12345678"

    # Simulate uvicorn access log record
    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname="uvicorn/protocols/http/httptools_impl.py",
        lineno=450,
        msg='127.0.0.1:51234 - "POST /v1beta/models?key=%s HTTP/1.1" 200',
        args=(gemini_key,),
        exc_info=None,
    )
    filter_instance.filter(record)
    assert gemini_key not in str(record.args)
    assert "[REDACTED]" in str(record.args)

    # Simulate uvicorn error log record
    err_record = logging.LogRecord(
        name="uvicorn.error",
        level=logging.ERROR,
        pathname="uvicorn/server.py",
        lineno=100,
        msg=f"Exception connecting upstream with Authorization: Bearer {groq_key}",
        args=(),
        exc_info=None,
    )
    filter_instance.filter(err_record)
    assert groq_key not in err_record.msg
    assert "[REDACTED]" in err_record.msg

