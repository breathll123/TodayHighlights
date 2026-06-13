from __future__ import annotations

import json
import logging
import re
import time
from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
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


class StructuredTextFormatter(logging.Formatter):
    def __init__(self, max_message_length: int = 4000, **kwargs):
        super().__init__(**kwargs)
        self.max_message_length = max_message_length

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, SH_TZ)
        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")
        ms = f"{int((record.created % 1) * 1000):03d}"

        level = record.levelname
        channel = getattr(record, "log_channel", "application")
        event = getattr(record, "event", record.getMessage())
        fields = dict(getattr(record, "event_fields", {}))

        parts = [f"{ts_str}.{ms}", level, f"channel={channel}", f"event={event}"]

        # category
        cat = fields.pop("category", None) or getattr(record, "category", None)
        if cat:
            parts.insert(3, f"category={cat}")

        # sorted fields
        for key in sorted(fields):
            val = fields[key]
            parts.append(f"{key}={_format_value(val)}")

        line = " ".join(parts)

        if len(line) > self.max_message_length:
            line = line[:self.max_message_length]
            line += " truncated=true"

        if record.exc_info and record.exc_info[1]:
            line += "\n" + self.formatException(record.exc_info)

        return line


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


# Rate-limited logging
_rate_limit_store: dict[str, float] = {}
_rate_limit_lock = __import__("threading").Lock()


def log_event_rate_limited(
    logger: logging.Logger,
    *,
    fingerprint: str,
    interval_seconds: float,
    **event_kwargs: Any,
) -> bool:
    now = time.monotonic()
    with _rate_limit_lock:
        last = _rate_limit_store.get(fingerprint, 0)
        if now - last < interval_seconds:
            return False
        _rate_limit_store[fingerprint] = now
        # Cleanup old entries
        if len(_rate_limit_store) > 256:
            expired = [k for k, v in _rate_limit_store.items() if now - v > interval_seconds * 4]
            for k in expired:
                del _rate_limit_store[k]
    log_event(logger, **event_kwargs)
    return True
