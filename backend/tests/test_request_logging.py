import logging
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.database import get_session
from app.core.logging import LoggingConfig, create_logging_runtime
from app.models.entities import User
from app.core.request_logging import install_request_logging
from app.services.auth_service import create_token


def _app(tmp_path: Path, *, trust_proxy=False):
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
    assert "http.completed HTTP请求完成" in text
    assert "request=req-123" in text
    assert "request_id=" not in text
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
    assert f"request={request_id[:8]}" in access
    assert "request_id=" not in access
    assert f"request_id={request_id}" in error
    assert "RuntimeError" in error
    assert "secret" not in error


def test_health_exclusion_produces_no_access_line(tmp_path):
    app, runtime = _app(tmp_path)
    # Reinstall with health excluded
    app.user_middleware.clear()
    install_request_logging(
        app, slow_request_ms=1, excluded_paths={"/health"}, trust_proxy_headers=False,
    )

    @app.get("/health")
    def health():
        return {"status": "ok"}

    try:
        TestClient(app).get("/health")
        TestClient(app).get("/ok")
    finally:
        runtime.stop()

    access = (tmp_path / "access.log").read_text()
    assert "/health" not in access
    assert "/ok" in access


def test_x_forwarded_for_ignored_by_default(tmp_path):
    app, runtime = _app(tmp_path)
    try:
        TestClient(app).get("/ok", headers={"X-Forwarded-For": "1.2.3.4"})
    finally:
        runtime.stop()

    text = (tmp_path / "access.log").read_text()
    assert "1.2.3.4" not in text


def test_x_forwarded_for_used_when_trusted(tmp_path):
    app, runtime = _app(tmp_path, trust_proxy=True)
    try:
        TestClient(app).get("/ok", headers={"X-Forwarded-For": "1.2.3.4"})
    finally:
        runtime.stop()

    text = (tmp_path / "access.log").read_text()
    assert "1.2.3.4" in text


def test_authenticated_access_log_contains_username_and_response_size(client, caplog):
    session = next(client.app.dependency_overrides[get_session]())
    user = User(
        username="admin",
        email=None,
        password_hash="hash",
        role="admin",
        status="active",
    )
    session.add(user)
    session.commit()
    token = create_token(user)
    caplog.set_level(logging.INFO)

    response = client.get(
        "/api/auth/me",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Request-ID": "request-readable-1234",
        },
    )

    assert response.status_code == 200
    record = next(
        record
        for record in caplog.records
        if getattr(record, "event", "") == "http.completed"
        and record.event_fields.get("path") == "/api/auth/me"
    )
    assert record.event_fields["username"] == "admin"
    assert record.event_fields["user_id"] == user.id
    assert record.event_fields["request"] == "request-"
    assert record.event_fields["response_bytes"] != "-"
    assert "request_id" not in record.event_fields


def test_access_log_normalizes_repeated_slashes_for_display(tmp_path):
    app, runtime = _app(tmp_path)
    try:
        TestClient(app).get("/api//ok")
    finally:
        runtime.stop()

    text = (tmp_path / "access.log").read_text()
    assert "path=/api/ok" in text
    assert "path=/api//ok" not in text
