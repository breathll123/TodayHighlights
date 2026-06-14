from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SENSITIVE_KEYS = {
    "api_key", "x-api-key", "authorization", "cookie", "set-cookie",
    "password", "secret", "token", "access_token", "refresh_token",
}

_SENSITIVE_URL_KEY_PARTS = (
    "token",
    "key",
    "secret",
    "password",
    "passwd",
    "authorization",
    "cookie",
    "session",
    "signature",
    "sign",
    "credential",
)
_SENSITIVE_URL_KEYS = {
    "auth",
    "auth_code",
    "oauth_code",
}
_SAFE_REQUEST_HEADER_NAMES = {
    "user-agent",
    "referer",
    "content-type",
    "accept",
}
_JSON_SENSITIVE_KEY_PATTERN = (
    r"api[_-]?key|x-api-key|access_token|refresh_token|authorization|cookie|"
    r"password|passwd|secret|token|session|signature|sign|credential|"
    r"(?:[a-z0-9]+[_-])+(?:secret|token|password|passwd|signature|credential)"
)
_JSON_PRIMITIVE_PATTERN = r"-?(?:\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|true|false|null)"
_JSON_SENSITIVE_FIELD_RE = re.compile(
    rf"""
    (?P<prefix>
        (?P<key_quote>["'])
        (?:{_JSON_SENSITIVE_KEY_PATTERN})
        (?P=key_quote)
        \s*:\s*
    )
    (?P<value>
        "(?:\\.|[^"\\])*"
        |
        '(?:\\.|[^'\\])*'
        |
        {_JSON_PRIMITIVE_PATTERN}
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)
_ESCAPED_JSON_SENSITIVE_FIELD_RE = re.compile(
    rf"""
    (?P<prefix>
        \\(?P<key_quote>["'])
        (?:{_JSON_SENSITIVE_KEY_PATTERN})
        \\(?P=key_quote)
        \s*:\s*
    )
    (?P<value>
        \\"(?:\\\\.|[^"\\])*\\"
        |
        \\'(?:\\\\.|[^'\\])*\\'
        |
        {_JSON_PRIMITIVE_PATTERN}
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _redact_json_field(match: re.Match[str], *, escaped: bool = False) -> str:
    value = match.group("value")
    if escaped and value.startswith(('\\"', "\\'")):
        replacement = f"\\{value[1]}[REDACTED]\\{value[1]}"
    elif value.startswith(("\"", "'")):
        replacement = f"{value[0]}[REDACTED]{value[0]}"
    else:
        replacement = r'\"[REDACTED]\"' if escaped else '"[REDACTED]"'
    return f"{match.group('prefix')}{replacement}"


def redact_text(value: str) -> str:
    text = value
    text = _ESCAPED_JSON_SENSITIVE_FIELD_RE.sub(
        lambda match: _redact_json_field(match, escaped=True),
        text,
    )
    text = _JSON_SENSITIVE_FIELD_RE.sub(_redact_json_field, text)
    text = re.sub(
        r"(?i)\b(mysql(?:\+pymysql)?|redis|rediss)://([^:/@\s]+):([^@\s]+)@",
        r"\1://\2:[REDACTED]@",
        text,
    )
    text = re.sub(
        rf"(?i)\b({_JSON_SENSITIVE_KEY_PATTERN})"
        r"\s*[:=]\s*(?:Bearer\s+)?[^\s,;&]+",
        lambda match: f"{match.group(1)}=[REDACTED]",
        text,
    )
    text = re.sub(r"(?i)(Bearer\s+)[^\s,;&]+", r"\1[REDACTED]", text)
    return text


def sanitize_fields(fields: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in fields.items():
        lowered = key.lower()
        credential_token = lowered.endswith(("_token", "-token"))
        if (
            lowered in SENSITIVE_KEYS
            or credential_token
            or any(part in lowered for part in ("password", "secret", "api_key"))
        ):
            sanitized[key] = "[REDACTED]"
        elif isinstance(value, str):
            sanitized[key] = redact_text(value)
        elif isinstance(value, dict):
            sanitized[key] = sanitize_fields(value)
        elif isinstance(value, (list, tuple)):
            sanitized[key] = [
                sanitize_fields({"value": item})["value"]
                if isinstance(item, (str, dict))
                else item
                for item in value
            ]
        else:
            sanitized[key] = value
    return sanitized


def sanitize_url(url: str, mode: str = "safe") -> str:
    parts = urlsplit(url)
    query_items = parse_qsl(parts.query, keep_blank_values=True)
    sanitized_items: list[tuple[str, str]] = []
    for key, value in query_items:
        lowered_key = key.lower()
        if mode == "keys":
            safe_value = "[PRESENT]"
        elif (
            lowered_key in _SENSITIVE_URL_KEYS
            or any(part in lowered_key for part in _SENSITIVE_URL_KEY_PARTS)
        ):
            safe_value = "[REDACTED]"
        else:
            safe_value = value
        sanitized_items.append((key, safe_value))

    query = urlencode(sanitized_items, doseq=True, safe="[]")
    netloc = parts.netloc.rsplit("@", 1)[-1]
    return urlunsplit((parts.scheme, netloc, parts.path, query, ""))


def safe_request_headers(headers: Mapping[str, Any] | None) -> dict[str, str]:
    if not headers:
        return {}
    sanitized: dict[str, str] = {}
    for key, value in headers.items():
        lowered_key = key.lower()
        if lowered_key not in _SAFE_REQUEST_HEADER_NAMES:
            continue
        text = str(value)
        sanitized[lowered_key] = (
            redact_text(sanitize_url(text))
            if lowered_key == "referer"
            else redact_text(text)
        )
    return sanitized


def response_preview(value: Any, max_chars: int = 500) -> str:
    if max_chars <= 0 or value is None:
        return ""
    raw = str(value).strip()
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        sanitized = redact_text(raw)
    else:
        sanitized = json.dumps(
            _redact_json_value(parsed),
            ensure_ascii=False,
            separators=(",", ":"),
        )
    collapsed = re.sub(r"\s+", " ", sanitized).strip()
    return collapsed[:max_chars]


def _redact_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): (
                "[REDACTED]"
                if re.fullmatch(_JSON_SENSITIVE_KEY_PATTERN, str(key), re.IGNORECASE)
                else _redact_json_value(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_json_value(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value
