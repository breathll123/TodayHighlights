from app.core.database import get_session
from app.models.entities import AITokenUsage, User
from app.services.auth_service import create_token


def _admin_token(session):
    admin = User(username="admin", email=None, password_hash="hash", role="admin", status="active")
    session.add(admin)
    session.commit()
    return create_token(admin)


def test_admin_lists_users_and_can_disable_user(client):
    session = next(client.app.dependency_overrides[get_session]())
    token = _admin_token(session)
    user = User(username="alice", email=None, password_hash="hash", role="user", status="active")
    session.add(user)
    session.commit()

    users = client.get("/api/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert users.status_code == 200
    assert any(item["username"] == "alice" for item in users.json())

    disabled = client.patch(
        f"/api/admin/users/{user.id}",
        json={"status": "disabled"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "disabled"


def test_admin_lists_token_usage(client):
    session = next(client.app.dependency_overrides[get_session]())
    token = _admin_token(session)
    user = session.query(User).filter(User.username == "admin").one()
    session.add(AITokenUsage(user_id=user.id, model_name="free", usage_type="block_analysis", total_tokens=42, request_status="success"))
    session.commit()

    response = client.get("/api/admin/ai/token-usages", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["items"][0]["total_tokens"] == 42
