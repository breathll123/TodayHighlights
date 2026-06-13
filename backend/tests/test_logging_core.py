import logging
from io import StringIO
from pathlib import Path
from queue import Queue

from app.core.logging import (
    LoggingConfig,
    SafeQueueHandler,
    StructuredTextFormatter,
    bind_log_context,
    build_event_record,
    create_logging_runtime,
    log_event,
    redact_text,
    sanitize_fields,
)


def test_logging_settings_have_production_defaults():
    from app.core.config import Settings
    # Check field defaults directly (os.environ may override via conftest)
    fields = Settings.model_fields
    assert fields["log_dir"].default == "logs"
    assert fields["log_level"].default == "INFO"
    assert fields["log_rotation"].default == "daily"
    assert fields["log_retention_days"].default == 14
    assert fields["log_max_message_length"].default == 4000
    assert fields["log_console_enabled"].default is True
    assert fields["log_slow_request_ms"].default == 2000
    assert fields["log_trust_proxy_headers"].default is False


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
    lines = text.splitlines()
    assert "INFO" in lines[0]
    assert "crawler" in lines[0]
    assert "crawl_job_finished" in lines[0]
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
    assert len(text.splitlines()) == 2
    assert "truncated=true" in text
    assert len(text) < 220


# --- Runtime tests ---

def _config(tmp_path: Path, **overrides) -> LoggingConfig:
    values = {
        "log_dir": tmp_path,
        "level": logging.DEBUG,
        "rotation": "daily",
        "retention_days": 14,
        "max_message_length": 4000,
        "console_enabled": False,
        "queue_size": 32,
    }
    values.update(overrides)
    return LoggingConfig(**values)


def test_runtime_routes_each_event_to_one_file(tmp_path):
    runtime = create_logging_runtime(_config(tmp_path))
    runtime.start()
    try:
        logger = logging.getLogger("test.routing")
        log_event(logger, channel="access", event="http_request_completed", status=200)
        log_event(logger, channel="application", category="crawler", event="crawl_finished")
        log_event(logger, channel="error", event="unhandled_exception", level=logging.ERROR)
    finally:
        runtime.stop()

    access = (tmp_path / "access.log").read_text()
    application = (tmp_path / "application.log").read_text()
    error = (tmp_path / "error.log").read_text()
    assert "http_request_completed" in access
    assert "crawl_finished" not in access
    assert "crawl_finished" in application
    assert "unhandled_exception" not in application
    assert "unhandled_exception" in error


def test_hourly_and_daily_rotation_configuration(tmp_path):
    daily = create_logging_runtime(_config(tmp_path / "daily", rotation="daily"))
    daily.start()
    hourly = create_logging_runtime(_config(tmp_path / "hourly", rotation="hourly"))
    hourly.start()
    try:
        assert daily.file_handlers[0].when == "MIDNIGHT"
        assert hourly.file_handlers[0].when == "H"
        assert daily.file_handlers[0].backupCount == 14
        assert hourly.file_handlers[0].backupCount == 14 * 24
    finally:
        daily.stop()
        hourly.stop()


def test_console_event_is_emitted_once(tmp_path):
    stream = StringIO()
    runtime = create_logging_runtime(_config(tmp_path, console_enabled=True))
    runtime.start()
    assert runtime.console_handler is not None
    runtime.console_handler.setStream(stream)
    try:
        log_event(logging.getLogger("test.console"), event="console_once")
    finally:
        runtime.stop()

    assert stream.getvalue().count("console_once") == 1


def test_queue_overflow_warning_uses_direct_fallback():
    queue = Queue(maxsize=1)
    queue.put(build_event_record(logging.INFO, channel="application", event="already_full"))
    stream = StringIO()
    fallback = logging.StreamHandler(stream)
    fallback.setFormatter(StructuredTextFormatter())
    handler = SafeQueueHandler(queue, error_fallback=fallback)

    handler.enqueue(
        build_event_record(logging.INFO, channel="application", event="dropped_event")
    )

    text = stream.getvalue()
    assert "logging_queue_full" in text
    assert "dropped_event" not in text


def test_unwritable_directory_falls_back_to_console(monkeypatch, tmp_path):
    def fail_mkdir(*args, **kwargs):
        raise PermissionError("read-only")

    monkeypatch.setattr(Path, "mkdir", fail_mkdir)
    runtime = create_logging_runtime(_config(tmp_path, console_enabled=True))
    runtime.start()
    try:
        assert runtime.file_logging_enabled is False
        assert runtime.console_handler is not None
    finally:
        runtime.stop()


def test_error_record_preserves_exception_stack(tmp_path):
    runtime = create_logging_runtime(_config(tmp_path))
    runtime.start()
    try:
        logger = logging.getLogger("test.exception")
        try:
            raise RuntimeError("boom")
        except RuntimeError:
            log_event(
                logger,
                channel="error",
                event="unhandled_exception",
                level=logging.ERROR,
                exc_info=True,
            )
    finally:
        runtime.stop()

    text = (tmp_path / "error.log").read_text()
    assert "RuntimeError: boom" in text
    assert "Traceback" in text


def test_error_stack_redacts_connection_credentials(tmp_path):
    runtime = create_logging_runtime(_config(tmp_path))
    runtime.start()
    try:
        try:
            raise RuntimeError("mysql+pymysql://user:secret-value@db/app")
        except RuntimeError:
            log_event(
                logging.getLogger("test.exception.redaction"),
                channel="error",
                event="unhandled_exception",
                level=logging.ERROR,
                exc_info=True,
            )
    finally:
        runtime.stop()

    text = (tmp_path / "error.log").read_text()
    assert "secret-value" not in text
    assert "[REDACTED]" in text
