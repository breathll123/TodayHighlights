from __future__ import annotations

import copy
import json
import logging
import logging.handlers
import os
import re
import sys
import threading
import time
from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from queue import Full, Queue
from typing import Any, Callable, Iterator

from app.core.config import SH_TZ
from app.core.logging_catalog import event_spec

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
    # Resolve exc_info=True to sys.exc_info()
    ei = sys.exc_info() if exc_info is True else exc_info
    record = logging.LogRecord(logger_name, level, "", 0, event, (), ei)
    record.log_channel = channel
    record.event = event
    record.event_fields = sanitize_fields(event_fields)
    return record


class StructuredTextFormatter(logging.Formatter):
    LEVEL_WIDTH = 8
    CATEGORY_WIDTH = 12

    def __init__(self, max_message_length: int = 4000, **kwargs):
        super().__init__(**kwargs)
        self.max_message_length = max_message_length

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, SH_TZ)
        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")
        ms = f"{int((record.created % 1) * 1000):03d}"

        level = record.levelname
        channel = getattr(record, "log_channel", "application")
        event = redact_text(str(getattr(record, "event", record.getMessage())))
        fields = sanitize_fields(dict(getattr(record, "event_fields", {})))
        cat = fields.pop("category", None) or getattr(record, "category", None)
        category = str(cat or channel)
        spec = event_spec(event)
        headline_event = _headline_token(event)
        headline_category = _headline_token(category)
        headline_description = _headline_token(spec.description)
        lines = [
            f"{ts_str}.{ms} {level:<{self.LEVEL_WIDTH}} "
            f"{headline_category:<{self.CATEGORY_WIDTH}} "
            f"{headline_event} {headline_description}"
        ]

        expanded = set(spec.expanded_fields)
        regular_fields = {
            key: value for key, value in fields.items() if key not in expanded
        }
        ordered_keys = _ordered_field_names(regular_fields, spec.field_order)
        if ordered_keys:
            details = " ".join(
                f"{key}={_format_value(regular_fields[key])}" for key in ordered_keys
            )
            lines.append(f"  {details}")

        for key in spec.expanded_fields:
            if key in fields:
                lines.append(f"  {key}={_format_value(fields[key])}")

        text = "\n".join(lines)
        if len(text) > self.max_message_length:
            text = text[:self.max_message_length].rstrip()
            text += " truncated=true"

        if record.exc_info and record.exc_info[1]:
            exc_text = redact_text(self.formatException(record.exc_info))
            text += "\n" + exc_text
        elif getattr(record, "exc_text", None):
            text += "\n" + redact_text(record.exc_text)

        return text


def _headline_token(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()


def _ordered_field_names(
    fields: dict[str, Any],
    field_order: tuple[str, ...],
) -> list[str]:
    ordered = [key for key in field_order if key in fields]
    ordered.extend(key for key in fields if key not in field_order)
    return ordered


def _format_value(val: Any) -> str:
    if val is None:
        return "-"
    if isinstance(val, bool):
        return str(val).lower()
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, (dict, list)):
        return json.dumps(val, ensure_ascii=False, separators=(",", ":"))
    s = str(val)
    if any(c in s for c in (" ", "\n", "\t", '"')):
        return json.dumps(s, ensure_ascii=False)
    return s


def log_event(
    logger: logging.Logger,
    *,
    channel: str = "application",
    event: str = "log",
    level: int = logging.INFO,
    category: str | None = None,
    exc_info=None,
    **fields: Any,
) -> None:
    record = build_event_record(
        level, channel=channel, event=event, category=category, exc_info=exc_info, **fields
    )
    logger.handle(record)


def observed_http_get(
    get: Callable[..., Any],
    url: str,
    *,
    provider: str,
    operation: str,
    host: str,
    path: str,
    **kwargs: Any,
) -> Any:
    """Execute one HTTP GET while logging only allowlisted request metadata."""
    started = time.perf_counter()
    logger = logging.getLogger("today_highlights.external")
    try:
        response = get(url, **kwargs)
    except Exception as exc:
        log_event(
            logger,
            channel="application",
            category="crawler",
            event="external_request_failed",
            level=logging.WARNING,
            provider=provider,
            operation=operation,
            host=host,
            path=path,
            stage="transport",
            exception_type=type(exc).__name__,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        raise

    status = int(getattr(response, "status_code", 0) or 0)
    failed = status >= 400
    log_event(
        logger,
        channel="application",
        category="crawler",
        event="external_request_failed" if failed else "external_request_finished",
        level=logging.WARNING if failed else logging.INFO,
        provider=provider,
        operation=operation,
        host=host,
        path=path,
        stage="status" if failed else "response",
        status=status,
        duration_ms=round((time.perf_counter() - started) * 1000, 2),
    )
    return response


# Rate-limited logging
_rate_limit_store: dict[str, float] = {}
_rate_limit_lock = threading.Lock()


def _rate_limit_allows(fingerprint: str, interval_seconds: float) -> bool:
    now = time.monotonic()
    with _rate_limit_lock:
        last = _rate_limit_store.get(fingerprint, 0)
        if now - last < interval_seconds:
            return False
        _rate_limit_store[fingerprint] = now
        if len(_rate_limit_store) > 256:
            expired = [k for k, v in _rate_limit_store.items() if now - v > interval_seconds * 4]
            for key in expired:
                del _rate_limit_store[key]
    return True


def log_event_rate_limited(
    logger: logging.Logger,
    *,
    fingerprint: str,
    interval_seconds: float,
    **event_kwargs: Any,
) -> bool:
    if not _rate_limit_allows(fingerprint, interval_seconds):
        return False
    log_event(logger, **event_kwargs)
    return True


def log_adapter_failure(
    *,
    provider: str,
    operation: str,
    stage: str,
    exc: Exception,
) -> None:
    log_event_rate_limited(
        logging.getLogger("today_highlights.external"),
        fingerprint=f"adapter:{provider}:{operation}:{stage}:{type(exc).__name__}",
        interval_seconds=30,
        channel="application",
        category="crawler",
        event="adapter_operation_failed",
        level=logging.WARNING,
        provider=provider,
        operation=operation,
        stage=stage,
        exception_type=type(exc).__name__,
    )


# ---------------------------------------------------------------------------
# Logging runtime
# ---------------------------------------------------------------------------

_logging_runtime: LoggingRuntime | None = None
_logging_lock = threading.Lock()


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


class SafeQueueHandler(logging.handlers.QueueHandler):
    def __init__(self, queue, *, error_fallback=None):
        super().__init__(queue)
        self._error_fallback = error_fallback
        self._fallback_used = False

    def prepare(self, record: logging.LogRecord) -> logging.LogRecord:
        rec = copy.copy(record)
        rec.event_fields = dict(getattr(record, "event_fields", {}))
        if record.exc_info and not isinstance(record.exc_info, bool) and record.exc_info[1]:
            rec.exc_text = self.formatter.formatException(record.exc_info) if hasattr(self, "formatter") and self.formatter else ""
        resolved = None
        if record.args:
            resolved = record.getMessage()
            rec.msg = resolved
        if not hasattr(record, "event"):
            rec.event = resolved if resolved is not None else record.getMessage()
        rec.args = None
        return rec

    def enqueue(self, record: logging.LogRecord) -> None:
        try:
            self.queue.put_nowait(record)
        except Full:
            if record.levelno >= logging.ERROR and self._error_fallback:
                self._error_fallback.handle(record)
            elif self._error_fallback and _rate_limit_allows("queue-full", 30):
                self._error_fallback.handle(
                    build_event_record(
                        logging.WARNING,
                        channel="error",
                        event="logging_queue_full",
                    )
                )


class LoggingRuntime:
    def __init__(self, config: LoggingConfig):
        self.config = config
        self.queue: Queue | None = None
        self.listener: logging.handlers.QueueListener | None = None
        self.file_handlers: list[logging.FileHandler] = []
        self.console_handler: logging.StreamHandler | None = None
        self.file_logging_enabled = False
        self._saved_root_handlers: list[logging.Handler] = []
        self._saved_root_level: int = logging.WARNING
        self._error_fallback: logging.Handler | None = None

    def start(self) -> None:
        root = logging.getLogger()
        self._saved_root_handlers = list(root.handlers)
        self._saved_root_level = root.level
        root.handlers.clear()
        root.setLevel(self.config.level)

        # Console handler
        if self.config.console_enabled:
            self.console_handler = logging.StreamHandler(sys.stderr)
            self.console_handler.setLevel(self.config.level)
            fmtr = StructuredTextFormatter(max_message_length=self.config.max_message_length)
            self.console_handler.setFormatter(fmtr)

        # File handlers
        try:
            self.config.log_dir.mkdir(parents=True, exist_ok=True)
            rotation_when = "MIDNIGHT" if self.config.rotation == "daily" else "H"
            backup_count = (
                self.config.retention_days
                if self.config.rotation == "daily"
                else self.config.retention_days * 24
            )
            channels = ["access", "application", "error"]
            self.file_handlers = []
            for ch in channels:
                fh = logging.handlers.TimedRotatingFileHandler(
                    filename=str(self.config.log_dir / f"{ch}.log"),
                    when=rotation_when,
                    encoding="utf-8",
                    utc=False,
                    backupCount=backup_count,
                )
                fh.addFilter(ChannelFilter(ch))
                fh.setFormatter(StructuredTextFormatter(max_message_length=self.config.max_message_length))
                fh.setLevel(self.config.level)
                self.file_handlers.append(fh)
            # Error fallback for queue saturation
            self._error_fallback = logging.handlers.TimedRotatingFileHandler(
                filename=str(self.config.log_dir / "error.log"),
                when=rotation_when,
                encoding="utf-8",
                utc=False,
                backupCount=backup_count,
            )
            self._error_fallback.setFormatter(
                StructuredTextFormatter(max_message_length=self.config.max_message_length)
            )
            self._error_fallback.setLevel(logging.ERROR)
            self.file_logging_enabled = True
        except Exception:
            self.file_logging_enabled = False

        # Queue + listener
        self.queue = Queue(maxsize=self.config.queue_size)
        overflow_fallback = self._error_fallback or self.console_handler
        queue_handler = SafeQueueHandler(self.queue, error_fallback=overflow_fallback)
        queue_handler.setLevel(self.config.level)
        root.addHandler(queue_handler)

        targets: list[logging.Handler] = []
        if self.file_logging_enabled:
            targets.extend(self.file_handlers)
        if self.config.console_enabled and self.console_handler:
            targets.append(self.console_handler)
        if targets:
            self.listener = logging.handlers.QueueListener(self.queue, *targets, respect_handler_level=True)
            self.listener.start()

    def stop(self) -> None:
        if self.listener:
            self.listener.stop()
        root = logging.getLogger()
        root.handlers.clear()
        for h in self._saved_root_handlers:
            root.addHandler(h)
        root.setLevel(self._saved_root_level)
        for fh in self.file_handlers:
            try:
                fh.close()
            except Exception:
                pass
        if self._error_fallback is not None:
            try:
                self._error_fallback.close()
            except Exception:
                pass
            self._error_fallback = None
        self.file_handlers.clear()
        self.queue = None
        self.listener = None

    def close(self) -> None:
        self.stop()


def create_logging_runtime(config: LoggingConfig) -> LoggingRuntime:
    return LoggingRuntime(config)


def initialize_logging() -> None:
    global _logging_runtime
    from app.core.config import settings

    level_map = {"DEBUG": logging.DEBUG, "INFO": logging.INFO, "WARNING": logging.WARNING, "ERROR": logging.ERROR}
    log_level = level_map.get(settings.log_level.upper(), logging.INFO)

    config = LoggingConfig(
        log_dir=Path(settings.log_dir),
        level=log_level,
        rotation=settings.log_rotation if settings.log_rotation in ("daily", "hourly") else "daily",
        retention_days=max(1, settings.log_retention_days),
        max_message_length=max(100, settings.log_max_message_length),
        console_enabled=settings.log_console_enabled,
        queue_size=max(32, settings.log_queue_size),
    )
    runtime = create_logging_runtime(config)
    runtime.start()
    with _logging_lock:
        _logging_runtime = runtime
    log_event(logging.getLogger("today_highlights"), channel="application", event="application_started")


def shutdown_logging() -> None:
    global _logging_runtime
    with _logging_lock:
        runtime = _logging_runtime
        _logging_runtime = None
    if runtime:
        log_event(logging.getLogger("today_highlights"), channel="application", event="application_stopping")
        runtime.stop()


def logging_runtime() -> LoggingRuntime | None:
    return _logging_runtime
