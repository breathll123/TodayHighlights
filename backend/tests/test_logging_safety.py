from urllib.parse import parse_qsl, urlsplit

from app.core.logging import SENSITIVE_KEYS as exported_sensitive_keys
from app.core.logging import redact_text as exported_redact_text
from app.core.logging import sanitize_fields as exported_sanitize_fields
from app.core.logging_safety import (
    SENSITIVE_KEYS,
    redact_text,
    response_preview,
    safe_request_headers,
    sanitize_fields,
    sanitize_url,
)


def test_logging_reexports_safety_helpers():
    assert exported_sensitive_keys is SENSITIVE_KEYS
    assert exported_redact_text is redact_text
    assert exported_sanitize_fields is sanitize_fields


def test_sanitize_url_safe_keeps_regular_query_and_hides_sensitive_values():
    sanitized = sanitize_url(
        "https://provider.example/api/items?page=2&sort=hot&access_token=secret"
        "&ApiKey=private#debug",
    )

    parts = urlsplit(sanitized)
    assert parts.scheme == "https"
    assert parts.netloc == "provider.example"
    assert parts.path == "/api/items"
    assert parts.fragment == ""
    assert parse_qsl(parts.query, keep_blank_values=True) == [
        ("page", "2"),
        ("sort", "hot"),
        ("access_token", "[REDACTED]"),
        ("ApiKey", "[REDACTED]"),
    ]
    assert "secret" not in sanitized
    assert "private" not in sanitized


def test_sanitize_url_handles_repeated_and_empty_query_parameters():
    sanitized = sanitize_url(
        "https://provider.example/search?tag=one&tag=two&empty=&flag#fragment",
    )

    assert parse_qsl(urlsplit(sanitized).query, keep_blank_values=True) == [
        ("tag", "one"),
        ("tag", "two"),
        ("empty", ""),
        ("flag", ""),
    ]
    assert "#" not in sanitized


def test_sanitize_url_safe_preserves_values_for_regular_keys():
    sanitized = sanitize_url(
        "https://provider.example/search?q=authorization%3DBearer%20public-example",
    )

    assert parse_qsl(urlsplit(sanitized).query) == [
        ("q", "authorization=Bearer public-example"),
    ]


def test_sanitize_url_keys_mode_marks_every_query_value_present():
    sanitized = sanitize_url(
        "https://provider.example/search?q=markets&empty=&tag=one&tag=two",
        mode="keys",
    )

    assert parse_qsl(urlsplit(sanitized).query, keep_blank_values=True) == [
        ("q", "[PRESENT]"),
        ("empty", "[PRESENT]"),
        ("tag", "[PRESENT]"),
        ("tag", "[PRESENT]"),
    ]
    assert "markets" not in sanitized


def test_safe_request_headers_keeps_allowlist_and_redacts_values():
    headers = safe_request_headers(
        {
            "User-Agent": "DataFlow/1.0 token=agent-secret",
            "Referer": "https://provider.example/items?token=referer-secret",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": "Bearer authorization-secret",
            "Cookie": "session=cookie-secret",
            "X-Debug": "debug-secret",
        }
    )

    assert set(headers) == {"user-agent", "referer", "content-type", "accept"}
    assert "agent-secret" not in str(headers)
    assert "referer-secret" not in str(headers)
    assert "authorization-secret" not in str(headers)
    assert "cookie-secret" not in str(headers)
    assert "debug-secret" not in str(headers)


def test_response_preview_redacts_collapses_whitespace_and_truncates():
    preview = response_preview(
        "  authorization=Bearer private-value \n bad\t gateway response body  ",
        max_chars=42,
    )

    assert preview == "authorization=[REDACTED] bad gateway respo"
    assert "private-value" not in preview
    assert "\n" not in preview
    assert "\t" not in preview
    assert len(preview) == 42


def test_response_preview_returns_empty_when_disabled():
    assert response_preview("secret token=value", max_chars=0) == ""
    assert response_preview("secret token=value", max_chars=-1) == ""
