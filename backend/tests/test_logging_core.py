import logging

from app.core.logging import (
    StructuredTextFormatter,
    bind_log_context,
    build_event_record,
    redact_text,
    sanitize_fields,
)


def test_logging_settings_have_production_defaults():
    from app.core.config import settings

    assert settings.log_dir == "logs"
    assert settings.log_level == "INFO"
    assert settings.log_rotation == "daily"
    assert settings.log_retention_days == 14
    assert settings.log_max_message_length == 4000
    assert settings.log_console_enabled is True
    assert settings.log_slow_request_ms == 2000
    assert settings.log_trust_proxy_headers is False


def test_structured_formatter_merges_bound_context():
    formatter = StructuredTextFormatter(max_message_length=4000)

    with bind_log_context(request_id="req-12345678", crawl_job_id=42):
        record = build_event_record(
            logging.INFO,
            channel="application",
            category="crawler",
            event="crawl_job_finished",
            items_saved=6,
        )

    text = formatter.format(record)
    assert "INFO" in text
    assert "category=crawler" in text
    assert "event=crawl_job_finished" in text
    assert "request_id=req-12345678" in text
    assert "crawl_job_id=42" in text
    assert "items_saved=6" in text


def test_sensitive_fields_and_error_strings_are_redacted():
    fields = sanitize_fields({
        "api_key": "aa-secret",
        "Authorization": "Bearer abc.def",
        "database_url": "mysql+pymysql://user:password@127.0.0.1/db",
        "message": "x-api-key=secret-value redis://default:redispass@127.0.0.1:6379/0",
    })

    rendered = repr(fields)
    assert "aa-secret" not in rendered
    assert "abc.def" not in rendered
    assert "password" not in rendered
    assert "redispass" not in rendered
    assert rendered.count("[REDACTED]") >= 3

    assert "token-value" not in redact_text("Authorization: Bearer token-value")


def test_formatter_quotes_values_and_truncates_long_messages():
    formatter = StructuredTextFormatter(max_message_length=80)
    record = build_event_record(
        logging.WARNING,
        channel="application",
        category="crawler",
        event="crawl_failed",
        message="line one\nline two " + ("x" * 200),
    )

    text = formatter.format(record)
    assert "\n" not in text
    assert "truncated=true" in text
    assert len(text) < 220
