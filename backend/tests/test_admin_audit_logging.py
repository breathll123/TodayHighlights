import logging

from app.core.auth import verify_admin
from app.core.database import get_session
from app.models.entities import Topic, User
from app.services.auth_service import create_token


def _authenticated_admin(client):
    session = next(client.app.dependency_overrides[get_session]())
    admin = User(
        username="admin",
        email=None,
        password_hash="hash",
        role="admin",
        status="active",
    )
    topic = Topic(name="股票", slug="stocks", enabled=True)
    session.add_all([admin, topic])
    session.commit()
    client.app.dependency_overrides.pop(verify_admin, None)
    return session, topic, {
        "Authorization": f"Bearer {create_token(admin)}",
        "X-Request-ID": "audit-request-1234",
    }


def test_source_update_logs_operator_object_and_field_names(client, caplog):
    session, topic, headers = _authenticated_admin(client)
    created = client.post(
        "/api/admin/sources",
        headers=headers,
        json={
            "topic_id": topic.id,
            "site": "test",
            "name": "指数行情",
            "entry_url": "https://example.com",
            "cookie": "cookie-secret",
            "enabled": True,
            "crawl_interval_minutes": 60,
        },
    )
    assert created.status_code == 200
    caplog.clear()
    caplog.set_level(logging.INFO)

    response = client.put(
        f"/api/admin/sources/{created.json()['id']}",
        headers=headers,
        json={"enabled": False, "crawl_interval_minutes": 30},
    )

    assert response.status_code == 200
    record = next(r for r in caplog.records if getattr(r, "event", "") == "admin.changed")
    assert record.event_fields["username"] == "admin"
    assert record.event_fields["action"] == "update"
    assert record.event_fields["object_type"] == "source"
    assert record.event_fields["object_name"] == "指数行情"
    assert record.event_fields["object_id"] == created.json()["id"]
    assert record.event_fields["changed_fields"] == [
        "crawl_interval_minutes",
        "enabled",
    ]
    assert "cookie-secret" not in repr(record.event_fields)


def test_ai_model_audit_records_key_name_but_not_secret_value(client, caplog):
    _session, _topic, headers = _authenticated_admin(client)
    caplog.set_level(logging.INFO)

    response = client.post(
        "/api/admin/ai-models",
        headers=headers,
        json={
            "name": "DeepSeek 默认",
            "base_url": "https://api.example.com/v1",
            "model": "deepseek-chat",
            "api_key": "model-secret",
            "is_default": True,
            "enabled": True,
            "notes": "",
        },
    )

    assert response.status_code == 200
    record = next(r for r in caplog.records if getattr(r, "event", "") == "admin.changed")
    assert record.event_fields["object_type"] == "ai_model"
    assert record.event_fields["object_name"] == "DeepSeek 默认"
    assert "api_key" in record.event_fields["changed_fields"]
    assert "model-secret" not in repr(record.__dict__)
