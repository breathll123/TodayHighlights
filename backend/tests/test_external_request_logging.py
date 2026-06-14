import logging
from types import SimpleNamespace
from urllib.parse import parse_qsl, urlsplit

import pytest

import app.core.logging as logging_core
from app.core.logging import log_adapter_failure, observed_http_get


class _Response:
    def __init__(
        self,
        status_code: int,
        *,
        content: bytes = b"",
        text: str = "",
        headers: dict[str, str] | None = None,
    ):
        self.status_code = status_code
        self.content = content
        self.text = text
        self.headers = headers or {}


class _SparseResponse:
    status_code = 204


def _event_record(caplog, event: str):
    return next(
        record
        for record in caplog.records
        if getattr(record, "event", "") == event
    )


def _assert_record_excludes(record, *secrets: str):
    rendered = repr(record.__dict__)
    for secret in secrets:
        assert secret not in rendered


def test_observed_http_get_logs_safe_success_details(caplog):
    caplog.set_level(logging.INFO)

    response = observed_http_get(
        lambda _url, **_kwargs: _Response(
            200,
            content=b'{"ok":true}',
            text='{"ok":true}',
            headers={"CONTENT-TYPE": "application/json; charset=utf-8"},
        ),
        "https://provider.example/api/items?page=2&token=url-secret#debug",
        provider="example",
        operation="ranking",
        host="provider.example",
        path="/api/items",
        headers={
            "User-Agent": "DataFlow/1.0",
            "Authorization": "Bearer header-secret",
        },
    )

    assert response.status_code == 200
    record = _event_record(caplog, "upstream.completed")
    fields = record.event_fields
    assert fields["provider"] == "example"
    assert fields["operation"] == "ranking"
    assert fields["status"] == 200
    assert fields["response_bytes"] == len(b'{"ok":true}')
    assert fields["content_type"] == "application/json; charset=utf-8"
    assert fields["attempt"] == 1
    parts = urlsplit(fields["url"])
    assert parts.fragment == ""
    assert parse_qsl(parts.query, keep_blank_values=True) == [
        ("page", "2"),
        ("token", "[REDACTED]"),
    ]
    _assert_record_excludes(record, "url-secret", "header-secret")


def test_observed_http_get_logs_403_diagnostics(caplog, monkeypatch):
    caplog.set_level(logging.INFO)
    monkeypatch.setattr(
        logging_core,
        "settings",
        SimpleNamespace(
            log_url_query_mode="safe",
            log_response_preview_chars=64,
            log_detail_crawler=True,
        ),
        raising=False,
    )

    observed_http_get(
        lambda _url, **_kwargs: _Response(
            403,
            content=b"token=response-secret\n access denied",
            text="token=response-secret\n access denied",
            headers={"Content-Type": "text/plain"},
        ),
        "https://provider.example/api?view=full&session=url-session-secret",
        provider="example",
        operation="ranking",
        host="provider.example",
        path="/api",
        attempt=3,
        headers={
            "User-Agent": "DataFlow/1.0 token=agent-secret",
            "Referer": "https://client.example/?token=referer-secret",
            "Authorization": "Bearer authorization-secret",
            "Cookie": "session=cookie-secret",
        },
    )

    record = _event_record(caplog, "upstream.failed")
    fields = record.event_fields
    assert record.levelno == logging.WARNING
    assert fields["status"] == 403
    assert fields["stage"] == "status"
    assert fields["attempt"] == 3
    assert fields["response_bytes"] == len(b"token=response-secret\n access denied")
    assert fields["content_type"] == "text/plain"
    assert fields["response_preview"] == "token=[REDACTED] access denied"
    assert set(fields["request_headers"]) == {
        "user-agent",
        "referer",
    }
    assert parse_qsl(urlsplit(fields["url"]).query, keep_blank_values=True) == [
        ("view", "full"),
        ("session", "[REDACTED]"),
    ]
    _assert_record_excludes(
        record,
        "response-secret",
        "url-session-secret",
        "agent-secret",
        "referer-secret",
        "authorization-secret",
        "cookie-secret",
    )


def test_observed_http_get_redacts_403_json_body(caplog, monkeypatch):
    caplog.set_level(logging.INFO)
    monkeypatch.setattr(
        logging_core,
        "settings",
        SimpleNamespace(
            log_url_query_mode="safe",
            log_response_preview_chars=500,
            log_detail_crawler=True,
        ),
        raising=False,
    )
    body = (
        '{"access_token":"json-access-secret","password":"json-password-secret",'
        '"signature":"json-signature-secret","status":403,"allowed":false}'
    )

    observed_http_get(
        lambda _url, **_kwargs: _Response(
            403,
            content=body.encode(),
            text=body,
            headers={"Content-Type": "application/json"},
        ),
        "https://provider.example/api",
        provider="example",
        operation="ranking",
        host="provider.example",
        path="/api",
    )

    fields = _event_record(caplog, "upstream.failed").event_fields
    assert fields["response_preview"] == (
        '{"access_token":"[REDACTED]","password":"[REDACTED]",'
        '"signature":"[REDACTED]","status":403,"allowed":false}'
    )
    for secret in (
        "json-access-secret",
        "json-password-secret",
        "json-signature-secret",
    ):
        assert secret not in repr(fields)


def test_observed_http_get_logs_transport_failure_and_reraises(caplog):
    caplog.set_level(logging.INFO)

    def fail(_url, **_kwargs):
        raise TimeoutError("token=exception-secret")

    with pytest.raises(TimeoutError, match="exception-secret"):
        observed_http_get(
            fail,
            "https://provider.example/api?q=markets&api_key=url-secret",
            provider="example",
            operation="ranking",
            host="provider.example",
            path="/api",
            attempt=2,
            headers={
                "Accept": "application/json",
                "Authorization": "Bearer header-secret",
            },
        )

    record = _event_record(caplog, "upstream.failed")
    assert record.levelno == logging.WARNING
    assert record.event_fields["stage"] == "transport"
    assert record.event_fields["error_type"] == "TimeoutError"
    assert record.event_fields["attempt"] == 2
    assert record.event_fields["request_headers"] == {"accept": "application/json"}
    _assert_record_excludes(record, "exception-secret", "url-secret", "header-secret")


def test_observed_http_get_accepts_sparse_response_fixture(caplog):
    caplog.set_level(logging.INFO)

    response = observed_http_get(
        lambda _url, **_kwargs: _SparseResponse(),
        "https://provider.example/health",
        provider="example",
        operation="health",
        host="provider.example",
        path="/health",
    )

    assert response.status_code == 204
    fields = _event_record(caplog, "upstream.completed").event_fields
    assert fields["response_bytes"] == 0
    assert fields["content_type"] == ""


def test_adapter_failure_logs_only_safe_metadata(caplog):
    caplog.set_level(logging.INFO)

    log_adapter_failure(
        provider="example",
        operation="ranking_parse",
        stage="parse",
        exc=ValueError("response contained token=secret"),
    )

    record = _event_record(caplog, "adapter.failed")
    assert record.event_fields["error_type"] == "ValueError"
    assert record.event_fields["stage"] == "parse"
    assert "secret" not in str(record.event_fields)
