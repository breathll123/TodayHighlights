# Production File Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add production-grade, searchable, rotating file logs for HTTP access, application workflows, and system errors without leaking credentials or blocking application work.

**Architecture:** Add one logging core that owns context, redaction, formatting, routing, queueing, rotation, retention, fallback, and rate limiting. FastAPI middleware writes access/error events; crawler, AI, scheduler, cache, media, and live-block boundaries write structured application events through the same API. Keep the current single-Uvicorn-worker deployment so file rotation and embedded APScheduler remain process-safe.

**Tech Stack:** Python 3.11, standard-library `logging`, `QueueHandler`, `QueueListener`, `TimedRotatingFileHandler`, `ContextVar`, FastAPI middleware, APScheduler listeners, Pytest.

---

## File Map

**Create**

- `backend/app/core/logging.py`: context, redaction, structured formatting, channel routing, queue listener, rotation, retention, fallback, rate limiting, lifecycle.
- `backend/app/core/request_logging.py`: request ID validation, FastAPI access middleware, unhandled HTTP exception boundary.
- `backend/tests/test_logging_core.py`: formatter, redaction, routing, truncation, rotation, fallback, queue saturation.
- `backend/tests/test_request_logging.py`: request ID, access records, 500 correlation, proxy behavior, sensitive-data exclusion.
- `backend/tests/test_crawl_logging.py`: crawler stage events and failure correlation.
- `backend/tests/test_ai_logging.py`: model request, token, validation, failure, and prompt secrecy.
- `backend/tests/test_scheduler_logging.py`: APScheduler lifecycle and listener events.
- `backend/tests/test_block_logging.py`: live-block timeout/failure events and context propagation.
- `backend/tests/test_logging_config.py`: environment examples and ignored log-directory coverage.

**Modify**

- `backend/app/core/config.py`: logging environment settings.
- `backend/app/main.py`: initialize/stop logging and install HTTP middleware.
- `backend/app/core/auth.py`: attach authenticated `user_id` to request state and logging context.
- `backend/app/core/scheduler.py`: scheduler lifecycle and execution listeners.
- `backend/app/core/cache.py`: Redis/cache events and rate-limited failures.
- `backend/app/services/jobs.py`: crawl task stage and result events.
- `backend/app/services/ai_client.py`: central model transport, latency, JSON, and token events.
- `backend/app/services/ai_enrichment.py`: create processing jobs before calls and bind `ai_job_id`.
- `backend/app/services/ai_block_analysis.py`: bind block-analysis job context and log validation/persistence stages.
- `backend/app/services/artificial_analysis/collector.py`: request/page/quota/snapshot events.
- `backend/app/services/artificial_analysis/sync.py`: sync-run and dataset events.
- `backend/app/services/media_cache.py`: cache hit/download/write/rollback events.
- `backend/app/services/blocks.py`: live-block timeout/failure events with block metadata.
- `backend/app/services/adapters/*.py`: replace silent live-adapter failures with provider/operation events.
- `backend/app/sources/*.py`: replace silent persisted-source failures with provider/operation events or propagation.
- `backend/tests/conftest.py`: isolate test log output and reset logging runtime.
- `backend/tests/test_cache.py`: cache observability assertions.
- `backend/tests/test_media_cache.py`: media observability and redaction assertions.
- `backend/tests/test_artificial_analysis_collector.py`: Artificial Analysis request/quota log assertions.
- `backend/tests/test_ai_block_analysis.py`: AI job correlation assertions.
- `backend/tests/test_jobs_ai_integration.py`: item-enrichment job correlation assertions.
- `backend/.env.example`: production logging variables.
- `.env.example`: top-level logging variables.
- `.gitignore`: ignore `backend/logs/`.
- `README.md`: deployment, startup flags, log files, grep/tail examples.
- `CLAUDE.md`: local test command and production startup command.

## Task 1: Add Logging Configuration and Structured Record Primitives

**Files:**

- Create: `backend/app/core/logging.py`
- Create: `backend/tests/test_logging_core.py`
- Modify: `backend/app/core/config.py`

- [ ] **Step 1: Write failing tests for settings, context, formatting, truncation, and redaction**

Add these tests to `backend/tests/test_logging_core.py`:

```python
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
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
cd backend
APP_SECRET_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= \
REDIS_ENABLED=false \
python -m pytest tests/test_logging_core.py -q
```

Expected: collection fails because `app.core.logging` and logging settings do not exist.

- [ ] **Step 3: Add logging settings**

Append to `Settings` in `backend/app/core/config.py`:

```python
    log_dir: str = "logs"
    log_level: str = "INFO"
    log_rotation: str = "daily"
    log_retention_days: int = 14
    log_max_message_length: int = 4000
    log_console_enabled: bool = True
    log_slow_request_ms: int = 2000
    log_access_exclude_paths: str = ""
    log_trust_proxy_headers: bool = False
    log_queue_size: int = 10_000
```

Validation belongs in the logging core, not Pydantic validators: unsupported levels fall back to `INFO`, unsupported rotation falls back to `daily`, and non-positive numeric values use documented defaults while emitting a startup warning.

- [ ] **Step 4: Implement context, redaction, and formatting primitives**

Create `backend/app/core/logging.py` with these public interfaces:

```python
from __future__ import annotations

import copy
import json
import logging
import re
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from typing import Any, Iterator

from app.core.config import SH_TZ

_LOG_CONTEXT: ContextVar[dict[str, Any]] = ContextVar("log_context", default={})
SENSITIVE_KEYS = {
    "api_key", "x-api-key", "authorization", "cookie", "set-cookie",
    "password", "secret", "token", "access_token", "refresh_token",
}


@contextmanager
def bind_log_context(**fields: Any) -> Iterator[None]:
    current = dict(_LOG_CONTEXT.get())
    current.update({key: value for key, value in fields.items() if value is not None})
    token = _LOG_CONTEXT.set(current)
    try:
        yield
    finally:
        _LOG_CONTEXT.reset(token)


def current_log_context() -> dict[str, Any]:
    return dict(_LOG_CONTEXT.get())


def redact_text(value: str) -> str:
    text = value
    text = re.sub(r"(?i)(Bearer\s+)[^\s,;]+", r"\1[REDACTED]", text)
    text = re.sub(
        r"(?i)\b(mysql(?:\+pymysql)?|redis|rediss)://([^:/@\s]+):([^@\s]+)@",
        r"\1://\2:[REDACTED]@",
        text,
    )
    text = re.sub(
        r"(?i)\b(api[_-]?key|x-api-key|authorization|cookie|password|secret|token)"
        r"\s*[:=]\s*[^\s,;]+",
        lambda match: f"{match.group(1)}=[REDACTED]",
        text,
    )
    return text


def sanitize_fields(fields: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in fields.items():
        lowered = key.lower()
        if lowered in SENSITIVE_KEYS or any(part in lowered for part in ("password", "secret", "token", "api_key")):
            sanitized[key] = "[REDACTED]"
        elif isinstance(value, str):
            sanitized[key] = redact_text(value)
        elif isinstance(value, dict):
            sanitized[key] = sanitize_fields(value)
        elif isinstance(value, (list, tuple)):
            sanitized[key] = [
                sanitize_fields({"value": item})["value"] if isinstance(item, (str, dict)) else item
                for item in value
            ]
        else:
            sanitized[key] = value
    return sanitized


def build_event_record(
    level: int,
    *,
    channel: str,
    event: str,
    category: str | None = None,
    logger_name: str = "today_highlights",
    exc_info=None,
    **fields: Any,
) -> logging.LogRecord:
    event_fields = current_log_context()
    event_fields.update(fields)
    if category:
        event_fields["category"] = category
    record = logging.LogRecord(logger_name, level, "", 0, event, (), exc_info)
    record.log_channel = channel
    record.event = event
    record.event_fields = sanitize_fields(event_fields)
    return record
```

Implement `StructuredTextFormatter` so it:

- formats timestamps with `datetime.fromtimestamp(record.created, SH_TZ)` and milliseconds;
- emits level, optional category, event, then sorted fields;
- renders `None` as `-`, booleans as lowercase, dict/list as compact JSON;
- quotes and escapes whitespace/newlines with `json.dumps(..., ensure_ascii=False)`;
- truncates the event payload at `max_message_length` and appends `truncated=true`;
- appends formatted exception text only when `record.exc_info` or preserved `record.exc_text` exists.

- [ ] **Step 5: Run tests and verify GREEN**

Run:

```bash
cd backend
APP_SECRET_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= \
REDIS_ENABLED=false \
python -m pytest tests/test_logging_core.py -q
```

Expected: 4 tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/config.py backend/app/core/logging.py backend/tests/test_logging_core.py
git commit -m "feat: add structured logging primitives"
```

## Task 2: Add Queueing, File Routing, Rotation, Retention, and Fallback

**Files:**

- Modify: `backend/app/core/logging.py`
- Modify: `backend/tests/test_logging_core.py`
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: Add failing runtime tests**

Append tests that create an isolated runtime in `tmp_path`:

```python
import logging
from pathlib import Path

from app.core.logging import (
    LoggingConfig,
    create_logging_runtime,
    log_event,
)


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
    hourly = create_logging_runtime(_config(tmp_path / "hourly", rotation="hourly"))

    assert daily.file_handlers[0].when == "MIDNIGHT"
    assert hourly.file_handlers[0].when == "H"
    assert daily.file_handlers[0].backupCount == 14


def test_unwritable_directory_falls_back_to_console(monkeypatch, tmp_path):
    def fail_mkdir(*args, **kwargs):
        raise PermissionError("read-only")

    monkeypatch.setattr(Path, "mkdir", fail_mkdir)
    runtime = create_logging_runtime(_config(tmp_path))

    assert runtime.file_logging_enabled is False
    assert runtime.console_handler is not None


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
```

Add a bounded-queue test using a fake queue whose `put_nowait` raises `queue.Full`; assert an `INFO` record returns immediately and an `ERROR` record is written exactly once through the synchronous fallback.

- [ ] **Step 2: Run tests and verify RED**

Run the same `test_logging_core.py` command.

Expected: imports for `LoggingConfig`, `create_logging_runtime`, and `log_event` fail.

- [ ] **Step 3: Implement runtime types and handlers**

Add:

```python
from dataclasses import dataclass
from logging.handlers import QueueHandler, QueueListener, TimedRotatingFileHandler
from pathlib import Path
from queue import Full, Queue
import sys
import threading


@dataclass(frozen=True)
class LoggingConfig:
    log_dir: Path
    level: int
    rotation: str
    retention_days: int
    max_message_length: int
    console_enabled: bool
    queue_size: int


class ChannelFilter(logging.Filter):
    def __init__(self, channel: str):
        super().__init__()
        self.channel = channel

    def filter(self, record: logging.LogRecord) -> bool:
        assigned = getattr(record, "log_channel", None)
        if assigned is None:
            assigned = "error" if record.levelno >= logging.ERROR else "application"
        return assigned == self.channel
```

Implement:

- `SafeQueueHandler.prepare()` using `copy.copy(record)`, sanitizing `event_fields`, preserving a rendered `exc_text`, and clearing only unneeded unpickleable arguments.
- `SafeQueueHandler.enqueue()` with `put_nowait`; on `Full`, drop below-ERROR records and rate-limit a stderr warning; for ERROR, write once to `error_fallback_handler`.
- `LoggingRuntime.start()` to attach one queue handler to the root logger and start one listener.
- `LoggingRuntime.stop()` to flush, stop listener, close file handlers, and restore prior root handlers and level.
- one `TimedRotatingFileHandler` per file with `encoding="utf-8"`, `utc=False`, `backupCount=retention_days`, and suffix `%Y-%m-%d` or `%Y-%m-%d_%H`;
- startup cleanup matching only `access.log.*`, `application.log.*`, and `error.log.*` older than retention;
- `log_event()` that creates a normal logger record with `extra={"log_channel": ..., "event": ..., "event_fields": ...}` rather than bypassing logger filters;
- idempotent global `initialize_logging()`, `shutdown_logging()`, and `logging_runtime()`.

Do not add a second all-purpose file handler.

- [ ] **Step 4: Isolate logging during tests**

At the top of `backend/tests/conftest.py`, before importing `app.main`, add:

```python
import tempfile
from pathlib import Path

_TEST_LOG_DIR = Path(tempfile.gettempdir()) / "today-highlights-test-logs"
os.environ.setdefault("LOG_DIR", str(_TEST_LOG_DIR))
os.environ.setdefault("LOG_CONSOLE_ENABLED", "false")
os.environ.setdefault("LOG_RETENTION_DAYS", "1")
```

Add an autouse fixture that calls `shutdown_logging()` after each test only when a runtime exists. It must not delete another test's `caplog` handler before assertions; runtime restoration happens during fixture teardown.

- [ ] **Step 5: Run tests and verify GREEN**

Run:

```bash
cd backend
APP_SECRET_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= \
REDIS_ENABLED=false \
python -m pytest tests/test_logging_core.py -q
```

Expected: all core logging tests pass without files appearing under `backend/logs/`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/logging.py backend/tests/test_logging_core.py backend/tests/conftest.py
git commit -m "feat: add rotating queued file logs"
```

## Task 3: Add FastAPI Request IDs, Access Logs, and Error Correlation

**Files:**

- Create: `backend/app/core/request_logging.py`
- Create: `backend/tests/test_request_logging.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/core/auth.py`

- [ ] **Step 1: Write failing middleware tests**

Use a temporary FastAPI app with the middleware factory:

```python
import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.logging import LoggingConfig, create_logging_runtime
from app.core.request_logging import install_request_logging


def _app(tmp_path, *, trust_proxy=False):
    runtime = create_logging_runtime(LoggingConfig(
        log_dir=tmp_path,
        level=logging.DEBUG,
        rotation="daily",
        retention_days=2,
        max_message_length=4000,
        console_enabled=False,
        queue_size=128,
    ))
    runtime.start()
    app = FastAPI()
    install_request_logging(
        app,
        slow_request_ms=1,
        excluded_paths=set(),
        trust_proxy_headers=trust_proxy,
    )

    @app.get("/ok")
    def ok():
        return {"ok": True}

    @app.get("/explode")
    def explode():
        raise RuntimeError("database_url=mysql+pymysql://u:secret@db/app")

    return app, runtime


def test_request_id_is_returned_and_access_log_has_no_query_values(tmp_path):
    app, runtime = _app(tmp_path)
    try:
        response = TestClient(app).get(
            "/ok?symbol=secret-value",
            headers={"X-Request-ID": "req-12345678", "Authorization": "Bearer hidden"},
        )
    finally:
        runtime.stop()

    assert response.headers["X-Request-ID"] == "req-12345678"
    text = (tmp_path / "access.log").read_text()
    assert "request_id=req-12345678" in text
    assert "query_keys=symbol" in text
    assert "secret-value" not in text
    assert "hidden" not in text


def test_invalid_request_id_is_replaced(tmp_path):
    app, runtime = _app(tmp_path)
    try:
        response = TestClient(app).get("/ok", headers={"X-Request-ID": "bad id"})
    finally:
        runtime.stop()

    assert response.headers["X-Request-ID"] != "bad id"
    assert len(response.headers["X-Request-ID"]) >= 16


def test_unhandled_500_is_correlated_between_access_and_error(tmp_path):
    app, runtime = _app(tmp_path)
    try:
        response = TestClient(app, raise_server_exceptions=False).get("/explode")
        request_id = response.headers["X-Request-ID"]
    finally:
        runtime.stop()

    assert response.status_code == 500
    access = (tmp_path / "access.log").read_text()
    error = (tmp_path / "error.log").read_text()
    assert f"request_id={request_id}" in access
    assert f"request_id={request_id}" in error
    assert "RuntimeError" in error
    assert "secret" not in error
```

Also test:

- `/health` exclusion produces no access line;
- `X-Forwarded-For` is ignored when `trust_proxy_headers=False`;
- it is used when true;
- `request.state.user_id = 7` is emitted after the endpoint returns.

- [ ] **Step 2: Run tests and verify RED**

Expected: `app.core.request_logging` does not exist.

- [ ] **Step 3: Implement request middleware**

Create `backend/app/core/request_logging.py` with:

```python
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{8,128}$")


def valid_request_id(value: str | None) -> bool:
    return bool(value and REQUEST_ID_PATTERN.fullmatch(value))


def new_request_id() -> str:
    return secrets.token_hex(16)


def install_request_logging(
    app: FastAPI,
    *,
    slow_request_ms: int,
    excluded_paths: set[str],
    trust_proxy_headers: bool,
) -> None:
    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID")
        if not valid_request_id(request_id):
            request_id = new_request_id()
        request.state.request_id = request_id
        started = time.perf_counter()
        status_code = 500

        with bind_log_context(request_id=request_id):
            try:
                response = await call_next(request)
                status_code = response.status_code
            except Exception:
                log_event(
                    logger,
                    channel="error",
                    event="unhandled_http_exception",
                    level=logging.ERROR,
                    exc_info=True,
                    method=request.method,
                    path=request.url.path,
                )
                response = JSONResponse(
                    status_code=500,
                    content={"detail": "Internal server error", "request_id": request_id},
                )

            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            response.headers["X-Request-ID"] = request_id
            if request.url.path not in excluded_paths:
                query_keys = ",".join(sorted(request.query_params.keys())) or "-"
                client_ip = request.client.host if request.client else "-"
                if trust_proxy_headers:
                    forwarded = request.headers.get("X-Forwarded-For", "")
                    if forwarded:
                        client_ip = forwarded.split(",", 1)[0].strip()
                log_event(
                    logger,
                    channel="access",
                    event="http_request_completed",
                    method=request.method,
                    path=request.url.path,
                    query_keys=query_keys,
                    status=status_code,
                    duration_ms=duration_ms,
                    client_ip=client_ip,
                    user_id=getattr(request.state, "user_id", "-"),
                    slow=duration_ms >= slow_request_ms,
                )
            return response
```

Do not log headers or bodies.

- [ ] **Step 4: Attach authenticated user ID**

Change `get_current_user` in `backend/app/core/auth.py` to accept `request: Request`, resolve the user, set:

```python
request.state.user_id = user.id
```

Then return the user. Do not decode tokens in middleware.

- [ ] **Step 5: Initialize logging before cache and scheduler**

In `backend/app/main.py`:

- call `initialize_logging()` as the first lifespan action;
- emit `application_started` to `application`;
- install request middleware once using settings;
- initialize cache and scheduler after logging;
- on shutdown emit `application_stopping`, stop background systems, then call `shutdown_logging()` last;
- parse `LOG_ACCESS_EXCLUDE_PATHS` as comma-separated exact paths.

Keep application construction import-safe: no file creation until lifespan starts.

- [ ] **Step 6: Run request and auth tests**

Run:

```bash
cd backend
APP_SECRET_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= \
REDIS_ENABLED=false \
python -m pytest tests/test_request_logging.py tests/test_auth.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/core/request_logging.py backend/app/main.py backend/app/core/auth.py backend/tests/test_request_logging.py
git commit -m "feat: add correlated HTTP access logs"
```

## Task 4: Instrument Crawl Jobs and Data Adapters

**Files:**

- Create: `backend/tests/test_crawl_logging.py`
- Modify: `backend/app/services/jobs.py`
- Modify: `backend/app/services/adapters/aihot.py`
- Modify: `backend/app/services/adapters/datalearner.py`
- Modify: `backend/app/services/adapters/dongqiudi.py`
- Modify: `backend/app/services/adapters/eastmoney.py`
- Modify: `backend/app/services/adapters/qiumiwu.py`
- Modify: `backend/app/services/adapters/qiumiwu_schedule.py`
- Modify: `backend/app/services/adapters/tonghuashun.py`
- Modify: `backend/app/services/adapters/xueqiu.py`
- Modify: `backend/app/sources/aihot.py`
- Modify: `backend/app/sources/datalearner.py`
- Modify: `backend/app/sources/dongqiudi.py`
- Modify: `backend/app/sources/eastmoney.py`
- Modify: `backend/app/sources/qiumiwu.py`
- Modify: `backend/app/sources/tonghuashun.py`
- Modify: `backend/app/sources/xueqiu.py`

- [ ] **Step 1: Write crawl boundary tests**

Create fixtures for one successful fake adapter and one failing adapter. Capture `application.log` and assert:

```python
def test_crawl_success_logs_stage_counts(db_session, configured_runtime, monkeypatch):
    monkeypatch.setattr("app.services.jobs.get_adapter", lambda site: FakeAdapter([
        RawItemDraft(...),
        RawItemDraft(...),
    ]))

    job = run_crawl_job(db_session, source_id, "manual")
    configured_runtime.stop()
    text = application_log.read_text()

    assert job.status == "success"
    assert f"crawl_job_id={job.id}" in text
    assert "event=crawl_job_started" in text
    assert "event=crawl_fetch_finished" in text
    assert "event=crawl_persist_finished" in text
    assert "items_found=2" in text
    assert "event=crawl_job_finished" in text


def test_crawl_failure_logs_stage_and_safe_error(db_session, configured_runtime, monkeypatch):
    monkeypatch.setattr(
        "app.services.jobs.get_adapter",
        lambda site: FailingAdapter("cookie=secret-value upstream 403"),
    )

    job = run_crawl_job(db_session, source_id, "scheduled")
    configured_runtime.stop()
    text = application_log.read_text()

    assert job.status == "failed"
    assert "event=crawl_job_failed" in text
    assert "stage=fetch" in text
    assert "secret-value" not in text
```

Also test a duplicate-running job logs `crawl_job_skipped reason=already_running`.

- [ ] **Step 2: Verify tests fail**

Run:

```bash
python -m pytest tests/test_crawl_logging.py -q
```

Expected: no structured crawl events exist.

- [ ] **Step 3: Add stage-aware crawl task logging**

In `run_crawl_job`:

- start `time.perf_counter()` before work;
- create and flush `CrawlJob`;
- wrap the body in `bind_log_context(crawl_job_id=job.id, source_id=source.id)`;
- maintain `stage = "decrypt" | "adapter" | "fetch" | "persist" | "enrichment"`;
- emit `crawl_job_started`, `crawl_fetch_finished`, `crawl_persist_finished`, `crawl_job_finished`, and `crawl_job_failed`;
- emit only counts and metadata, never cookie, entry URL query strings, or raw content;
- use `exception_type=type(exc).__name__` and `message=str(exc)`;
- preserve existing database job status behavior.

When an individual enrichment fails, replace `pass` with:

```python
log_event(
    logger,
    channel="application",
    category="crawler",
    event="crawl_enrichment_failed",
    level=logging.WARNING,
    stage="enrichment",
    enrichment_id=enrichment.id,
    exception_type=type(exc).__name__,
    message=str(exc),
)
```

- [ ] **Step 4: Derive persistence counts without changing the service contract**

Keep `save_raw_items(...) -> list[RawItem]` unchanged because existing tests and
candidate selection depend on that return type. In `run_crawl_job`, derive:

```python
items_received = len(drafts)
items_saved = len(raw_items)
items_deduplicated = max(0, items_received - items_saved)
```

Include these counts in `crawl_persist_finished`. This adds no query and does
not change deduplication or update behavior.

- [ ] **Step 5: Audit and instrument adapter exception boundaries**

For each file listed in this task:

1. add a module logger;
2. before each external call record `started = time.perf_counter()`;
3. after a response emit `external_request_finished` with:

```python
log_event(
    logger,
    channel="application",
    category="crawler",
    event="external_request_finished",
    provider="eastmoney",
    operation="index_snapshot",
    host="push2delay.eastmoney.com",
    path="/api/qt/ulist.np/get",
    status=response.status_code,
    duration_ms=round((time.perf_counter() - started) * 1000, 2),
)
```

4. in caught failures emit `external_request_failed` or `crawl_parse_failed` before returning fallback data;
5. do not log full URLs, params, cookies, response bodies, or content;
6. preserve intentional live-page fallback-to-empty behavior;
7. persisted source adapters should propagate fatal failures to `run_crawl_job` after logging, so the database job becomes failed.

Run this audit and resolve every result:

```bash
rg -n "except Exception" backend/app/services/adapters backend/app/sources
```

Every catch must either log, re-raise, or contain a comment proving it is a harmless cleanup path with a rate-limited debug event.

- [ ] **Step 6: Run crawl tests and existing adapter tests**

Run:

```bash
python -m pytest \
  tests/test_crawl_logging.py \
  tests/test_jobs_ai_integration.py \
  tests/test_market_indices.py \
  tests/test_qiumiwu_media_cache.py \
  tests/test_xueqiu_adapter.py -q
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/jobs.py backend/app/services/adapters \
  backend/app/sources backend/tests/test_crawl_logging.py
git commit -m "feat: add structured crawler logs"
```

## Task 5: Instrument AI Requests and Generation Jobs

**Files:**

- Create: `backend/tests/test_ai_logging.py`
- Modify: `backend/app/services/ai_client.py`
- Modify: `backend/app/services/ai_enrichment.py`
- Modify: `backend/app/services/ai_block_analysis.py`
- Modify: `backend/tests/test_ai_block_analysis.py`
- Modify: `backend/tests/test_jobs_ai_integration.py`

- [ ] **Step 1: Write failing AI secrecy and usage tests**

Test the central client with a fake response:

```python
def test_ai_client_logs_usage_without_prompts(tmp_path, runtime):
    async def fake_post(payload):
        return {
            "choices": [{"message": {"content": '{"title":"ok"}'}}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 5, "total_tokens": 17},
        }

    with bind_log_context(ai_job_id=91):
        result = asyncio.run(
            AIClient("https://example.com", "secret-key", "model-a", post_json=fake_post)
            .complete_json_with_usage("SYSTEM SECRET", "USER PRIVATE BODY")
        )

    runtime.stop()
    text = (tmp_path / "application.log").read_text()
    assert result.content == {"title": "ok"}
    assert "event=ai_request_started" in text
    assert "event=ai_request_finished" in text
    assert "ai_job_id=91" in text
    assert "total_tokens=17" in text
    assert "SYSTEM SECRET" not in text
    assert "USER PRIVATE BODY" not in text
    assert "secret-key" not in text
```

Add failure tests for:

- HTTP transport error logs `stage=transport`;
- invalid JSON logs `stage=decode`, output length, and exception type but not raw output;
- validation failures in item/block services log `stage=validation`;
- generated job ID appears in every AI event.

- [ ] **Step 2: Verify tests fail**

Run:

```bash
python -m pytest tests/test_ai_logging.py -q
```

- [ ] **Step 3: Instrument `AIClient`**

In `complete_json_with_usage`:

- emit `ai_request_started` before `_send`;
- measure full request and decode duration;
- on transport/HTTP exception emit `ai_request_failed stage=transport`;
- on JSON decode failure emit `ai_request_failed stage=decode output_chars=<len>`;
- on success emit `ai_request_finished` with model, duration, token counts, `usage_estimated`, output chars, and sorted top-level JSON keys;
- never include prompts, payload, output text, API key, or Authorization.

Use `urlparse(self.base_url).hostname` for provider host, not the full URL.

- [ ] **Step 4: Create AI jobs before model calls**

Refactor `process_item_enrichment` and `generate_topic_summary`:

- create `AIGenerationJob(status="processing")` and flush before calling AI;
- bind `ai_job_id=job.id`;
- update the same job to `succeeded` or `failed` instead of creating it afterward;
- preserve retry links and existing database fields;
- emit `ai_validation_finished` and `ai_persist_finished`;
- log model config ID and model name, not encrypted key or prompt.

In `analyze_block`, wrap the existing job body:

```python
with bind_log_context(ai_job_id=job.id, user_id=user.id):
    ...
```

Log explicit stages `resolve_data`, `request`, `validation`, and `persist`.

- [ ] **Step 5: Run AI tests**

Run:

```bash
python -m pytest \
  tests/test_ai_logging.py \
  tests/test_ai_block_analysis.py \
  tests/test_jobs_ai_integration.py \
  tests/test_ai_validation.py -q
```

Expected: all pass and no prompt text appears in temporary logs.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/ai_client.py backend/app/services/ai_enrichment.py \
  backend/app/services/ai_block_analysis.py backend/tests/test_ai_logging.py \
  backend/tests/test_ai_block_analysis.py backend/tests/test_jobs_ai_integration.py
git commit -m "feat: add correlated AI generation logs"
```

## Task 6: Instrument Artificial Analysis Sync and Scheduler

**Files:**

- Create: `backend/tests/test_scheduler_logging.py`
- Modify: `backend/app/core/scheduler.py`
- Modify: `backend/app/services/artificial_analysis/collector.py`
- Modify: `backend/app/services/artificial_analysis/sync.py`
- Modify: `backend/tests/test_artificial_analysis_collector.py`

- [ ] **Step 1: Write failing collector and scheduler tests**

Collector assertions:

```python
assert "category=ai" in text
assert "event=aa_page_collected" in text
assert "dataset_key=language_global" in text
assert "page=1" in text
assert "response_bytes=" in text
assert "quota_remaining=99" in text
assert "api-secret" not in text
assert "x-api-key" not in text
```

Scheduler assertions:

```python
def test_scheduler_listener_logs_execution_failure(tmp_path, runtime):
    scheduler = create_scheduler()
    event = JobExecutionEvent(
        code=EVENT_JOB_ERROR,
        job_id="crawl_enabled_sources",
        jobstore="default",
        scheduled_run_time=datetime.now(timezone.utc),
        exception=RuntimeError("scheduled boom"),
        traceback="trace",
    )

    handle_scheduler_event(event)
    runtime.stop()
    text = (tmp_path / "application.log").read_text()
    assert "event=scheduled_job_failed" in text
    assert "job_id=crawl_enabled_sources" in text
```

Also cover executed, missed, max-instances/skipped, scheduler started/stopped, missing API key, and active-run skip.

- [ ] **Step 2: Verify tests fail**

Run:

```bash
python -m pytest tests/test_artificial_analysis_collector.py tests/test_scheduler_logging.py -q
```

- [ ] **Step 3: Instrument Artificial Analysis collection**

For every page request:

- bind `ai_job_id` to the AA sync run ID;
- emit `aa_request_started`;
- emit `aa_page_collected` after raw snapshot persistence with dataset key, page, HTTP status, bytes, snapshot ID, duration, tier, quota remaining;
- emit `aa_request_failed` for rate limit, quota reserve, too-large response, decode, and transport stages;
- do not log headers except safe numeric quota fields;
- do not attach the response request object to logs.

- [ ] **Step 4: Instrument sync orchestration**

In `request_sync_run`, `execute_sync_run`, and `scheduled_sync`, emit:

- `aa_sync_requested`;
- `aa_sync_started`;
- `aa_dataset_started`;
- `aa_dataset_finished` with entry count and dataset ID;
- `aa_dataset_failed`;
- `aa_sync_finished` with completed/failed dataset counts and status;
- `aa_sync_skipped reason=lock|active_run|disabled|missing_api_key`;
- `aa_sync_failed` for fatal boundaries.

Use `bind_log_context(ai_job_id=run_id, user_id=requested_by_user_id)`.

- [ ] **Step 5: Add scheduler listener**

In `backend/app/core/scheduler.py`:

```python
from apscheduler.events import (
    EVENT_JOB_ERROR,
    EVENT_JOB_EXECUTED,
    EVENT_JOB_MAX_INSTANCES,
    EVENT_JOB_MISSED,
)


def handle_scheduler_event(event) -> None:
    if event.code == EVENT_JOB_EXECUTED:
        log_event(... event="scheduled_job_finished", job_id=event.job_id)
    elif event.code == EVENT_JOB_ERROR:
        log_event(
            ...,
            event="scheduled_job_failed",
            level=logging.ERROR,
            job_id=event.job_id,
            exception_type=type(event.exception).__name__ if event.exception else "-",
            message=str(event.exception or ""),
        )
    elif event.code == EVENT_JOB_MISSED:
        log_event(... event="scheduled_job_missed", level=logging.WARNING, job_id=event.job_id)
    else:
        log_event(... event="scheduled_job_skipped", level=logging.WARNING,
                  job_id=event.job_id, reason="max_instances")
```

Register the listener in `create_scheduler()`. Log the registered job IDs after creation, and emit start/stop events from `main.py`.

- [ ] **Step 6: Run tests**

Run:

```bash
python -m pytest \
  tests/test_artificial_analysis_collector.py \
  tests/test_artificial_analysis_api.py \
  tests/test_scheduler_logging.py -q
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/core/scheduler.py backend/app/services/artificial_analysis \
  backend/tests/test_artificial_analysis_collector.py backend/tests/test_scheduler_logging.py
git commit -m "feat: log scheduled and ranking sync jobs"
```

## Task 7: Instrument Cache, Media, Live Blocks, and Infrastructure Failures

**Files:**

- Modify: `backend/app/core/cache.py`
- Modify: `backend/app/services/media_cache.py`
- Modify: `backend/app/services/blocks.py`
- Modify: `backend/tests/test_cache.py`
- Modify: `backend/tests/test_media_cache.py`
- Create: `backend/tests/test_block_logging.py`

- [ ] **Step 1: Write failing infrastructure log tests**

Add assertions that:

- Redis initialization failure emits `category=cache event=cache_backend_fallback`;
- Redis recovery emits `cache_backend_recovered`;
- repeated identical Redis failures are rate-limited;
- SWR refresh failure includes function ID and exception type;
- media hit emits `media_cache_hit`;
- download emits `media_download_finished` with hash, bytes, duration;
- media rollback emits `media_cache_failed` without full signed URL;
- live block timeout emits `block_resolve_failed reason=timeout`;
- live block exception includes block ID/source type and request ID copied into the executor.

- [ ] **Step 2: Verify tests fail**

Run:

```bash
python -m pytest tests/test_cache.py tests/test_media_cache.py tests/test_block_logging.py -q
```

- [ ] **Step 3: Add a rate-limited event helper**

In `app/core/logging.py`, add:

```python
def log_event_rate_limited(
    logger: logging.Logger,
    *,
    fingerprint: str,
    interval_seconds: float,
    **event_kwargs,
) -> bool:
    ...
```

Use a bounded, thread-safe dictionary of last-emitted monotonic timestamps. Return `True` when emitted and `False` when suppressed. Never include secrets in the fingerprint.

- [ ] **Step 4: Replace cache silent catches**

For Redis get/set/lock/generation failures:

- emit rate-limited `cache_operation_failed`;
- fields: operation, backend, exception type, status;
- never include key, value, prefix, URL, lock token, or serialized arguments.

For initialization and recovery:

- `cache_backend_ready`;
- `cache_backend_fallback`;
- `cache_backend_recovered`.

For SWR:

- log `swr_refresh_failed` with function ID and exception type;
- preserve fallback behavior.

- [ ] **Step 5: Instrument media cache**

Add events at:

- unsafe URL skip;
- session creation failure;
- existing file hit;
- remote download completion;
- file write completion;
- unique-race reuse;
- rollback/file cleanup failure.

Use `url_hash`, provider, asset type, entity type, status, bytes, duration. Never log `source_url` or metadata values.

- [ ] **Step 6: Instrument live-block executor with copied context**

Before executor submission:

```python
ctx = copy_context()
future = executor.submit(ctx.run, resolve_block_data, None, block, cookie, media_cache)
```

Log block start only at DEBUG. On timeout/failure emit application events containing block ID, source type, route, duration, and reason. Unknown exceptions already handled at this boundary stay in `application.log`; executor-level escape goes to `error.log`.

- [ ] **Step 7: Run tests**

Run:

```bash
python -m pytest tests/test_cache.py tests/test_media_cache.py tests/test_block_logging.py tests/test_page_blocks.py -q
```

- [ ] **Step 8: Commit**

```bash
git add backend/app/core/logging.py backend/app/core/cache.py \
  backend/app/services/media_cache.py backend/app/services/blocks.py \
  backend/tests/test_cache.py backend/tests/test_media_cache.py backend/tests/test_block_logging.py
git commit -m "feat: log cache media and block failures"
```

## Task 8: Add Environment, Deployment, and Operations Documentation

**Files:**

- Modify: `backend/.env.example`
- Modify: `.env.example`
- Modify: `.gitignore`
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Create: `backend/tests/test_logging_config.py`

- [ ] **Step 1: Write config documentation test**

Read both example files and assert required keys exist:

```python
REQUIRED = {
    "LOG_DIR",
    "LOG_LEVEL",
    "LOG_ROTATION",
    "LOG_RETENTION_DAYS",
    "LOG_MAX_MESSAGE_LENGTH",
    "LOG_CONSOLE_ENABLED",
    "LOG_SLOW_REQUEST_MS",
    "LOG_ACCESS_EXCLUDE_PATHS",
    "LOG_TRUST_PROXY_HEADERS",
}
```

Assert `.gitignore` contains `backend/logs/`.

- [ ] **Step 2: Verify test fails**

Run:

```bash
python -m pytest tests/test_logging_config.py -q
```

- [ ] **Step 3: Add environment examples**

Append:

```env
# Production file logging
LOG_DIR=logs
LOG_LEVEL=INFO
LOG_ROTATION=daily
LOG_RETENTION_DAYS=14
LOG_MAX_MESSAGE_LENGTH=4000
LOG_CONSOLE_ENABLED=true
LOG_SLOW_REQUEST_MS=2000
LOG_ACCESS_EXCLUDE_PATHS=
LOG_TRUST_PROXY_HEADERS=false
LOG_QUEUE_SIZE=10000
```

For the current Nginx deployment, recommend:

```env
LOG_ACCESS_EXCLUDE_PATHS=/health
LOG_TRUST_PROXY_HEADERS=true
```

Only enable trusted proxy headers because Uvicorn binds to `127.0.0.1` and only local Nginx reaches it.

- [ ] **Step 4: Update deployment instructions**

Document:

```bash
cd /root/projects/daily_highlights/TodayHighlights/backend
mkdir -p logs
chmod 750 logs
```

BaoTa startup command:

```bash
python -m uvicorn app.main:app \
  --host 127.0.0.1 \
  --port 8000 \
  --workers 1 \
  --no-access-log
```

Operations:

```bash
tail -f logs/access.log
tail -f logs/application.log
tail -f logs/error.log
grep 'category=crawler' logs/application.log
grep 'category=ai' logs/application.log
grep 'crawl_job_id=128' logs/application.log
grep 'request_id=<id>' logs/access.log logs/error.log
```

Explain daily/hourly rotation, retention, file ownership, disk monitoring, and why workers must remain 1.

- [ ] **Step 5: Run test**

Run:

```bash
python -m pytest tests/test_logging_config.py -q
```

- [ ] **Step 6: Commit**

```bash
git add backend/.env.example .env.example .gitignore README.md CLAUDE.md backend/tests/test_logging_config.py
git commit -m "docs: document production logging operations"
```

## Task 9: Full Verification and Server Smoke Checklist

**Files:**

- Modify only if verification reveals defects.

- [ ] **Step 1: Run formatting and placeholder audits**

```bash
git diff --check
rg -n "except Exception:\\s*(pass|return \\[\\]|return \"\")" \
  backend/app/services backend/app/sources backend/app/core
```

Expected: no unexplained silent broad exceptions remain in the instrumented scope.

- [ ] **Step 2: Run the complete backend suite**

```bash
cd backend
APP_SECRET_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= \
REDIS_ENABLED=false \
python -m pytest tests -q --ignore=tests/test_gainers_api.py
```

Expected: all deterministic tests pass. Run `tests/test_gainers_api.py` separately only where outbound network access is available because it directly calls a third-party endpoint.

- [ ] **Step 3: Run a local application smoke test**

Start:

```bash
cd backend
python -m uvicorn app.main:app \
  --host 127.0.0.1 \
  --port 8001 \
  --workers 1 \
  --no-access-log
```

Exercise:

```bash
curl -i http://127.0.0.1:8001/health
curl -i http://127.0.0.1:8001/api/public/market-indices
curl -i -H 'X-Request-ID: smoke-12345678' http://127.0.0.1:8001/api/public/topics
```

Verify:

```bash
tail -n 20 logs/access.log
tail -n 50 logs/application.log
test ! -s logs/error.log || tail -n 50 logs/error.log
```

Expected: access records have request IDs and durations; market-index external request/crawler events contain no URL params; no credentials appear.

- [ ] **Step 4: Run a secret scan over generated logs**

```bash
rg -n \
  'Bearer [A-Za-z0-9._-]+|x-api-key=[^[]|mysql\\+pymysql://[^ ]+:[^[]|redis://[^ ]+:[^[]' \
  backend/logs
```

Expected: no matches.

- [ ] **Step 5: Test daily/hourly selection**

Run once with:

```bash
LOG_ROTATION=hourly LOG_RETENTION_DAYS=2 ...
```

Assert the active files are still named `access.log`, `application.log`, and `error.log`, and handler suffixes are hourly. Do not wait for real-time rollover; the automated handler configuration test is authoritative.

- [ ] **Step 6: Verify BaoTa deployment**

After pulling on the server:

```bash
cd /root/projects/daily_highlights/TodayHighlights/backend
mkdir -p logs
chmod 750 logs
```

Restart the Python project, then execute:

```bash
curl -i http://127.0.0.1:8000/health
curl -i http://8.130.152.32/health
tail -f logs/access.log
tail -f logs/application.log
tail -f logs/error.log
```

Trigger one manual source crawl and one AI operation. Confirm:

- HTTP request has a response `X-Request-ID`;
- manual crawl can be traced by `crawl_job_id`;
- AI call can be traced by `ai_job_id`;
- scheduler startup and registered jobs appear;
- Redis status appears without its URL;
- API keys, cookies, tokens, prompts, and article bodies do not appear.

- [ ] **Step 7: Commit verification-only fixes**

If no fixes were needed, do not create an empty commit. Otherwise:

```bash
git add <only-files-changed-by-verification>
git commit -m "fix: harden production logging verification"
```
