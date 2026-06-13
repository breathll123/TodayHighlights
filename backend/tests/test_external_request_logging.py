import logging

import pytest

from app.core.logging import log_adapter_failure, observed_http_get


class _Response:
    def __init__(self, status_code: int):
        self.status_code = status_code


def test_observed_http_get_logs_safe_success_metadata(caplog):
    caplog.set_level(logging.INFO)

    response = observed_http_get(
        lambda _url, **_kwargs: _Response(200),
        "https://provider.example/api?token=secret",
        provider="example",
        operation="ranking",
        host="provider.example",
        path="/api",
        headers={"Authorization": "Bearer secret"},
    )

    assert response.status_code == 200
    record = next(
        record
        for record in caplog.records
        if getattr(record, "event", "") == "external_request_finished"
    )
    assert record.event_fields["provider"] == "example"
    assert record.event_fields["operation"] == "ranking"
    assert record.event_fields["status"] == 200
    assert "secret" not in str(record.event_fields)


def test_observed_http_get_logs_transport_failure_and_reraises(caplog):
    caplog.set_level(logging.INFO)

    def fail(_url, **_kwargs):
        raise TimeoutError("upstream timeout")

    with pytest.raises(TimeoutError):
        observed_http_get(
            fail,
            "https://provider.example/api?token=secret",
            provider="example",
            operation="ranking",
            host="provider.example",
            path="/api",
        )

    record = next(
        record
        for record in caplog.records
        if getattr(record, "event", "") == "external_request_failed"
    )
    assert record.event_fields["stage"] == "transport"
    assert record.event_fields["exception_type"] == "TimeoutError"
    assert "secret" not in str(record.event_fields)


def test_adapter_failure_logs_only_safe_metadata(caplog):
    caplog.set_level(logging.INFO)

    log_adapter_failure(
        provider="example",
        operation="ranking_parse",
        stage="parse",
        exc=ValueError("response contained token=secret"),
    )

    record = next(
        record
        for record in caplog.records
        if getattr(record, "event", "") == "adapter_operation_failed"
    )
    assert record.event_fields["exception_type"] == "ValueError"
    assert record.event_fields["stage"] == "parse"
    assert "secret" not in str(record.event_fields)
