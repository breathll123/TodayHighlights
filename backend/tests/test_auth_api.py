from sqlalchemy import inspect

from app.core.database import get_session
from app.models.entities import User


def test_users_table_columns_exist(client):
    session = next(client.app.dependency_overrides[get_session]())
    columns = {col["name"] for col in inspect(session.bind).get_columns("users")}

    assert {
        "id",
        "username",
        "email",
        "password_hash",
        "role",
        "status",
        "last_login_at",
        "created_at",
        "updated_at",
    }.issubset(columns)


def test_register_login_and_me(client):
    register = client.post(
        "/api/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": "secret123"},
    )
    assert register.status_code == 200
    assert register.json()["user"]["role"] == "user"

    login = client.post("/api/auth/login", json={"login": "alice", "password": "secret123"})
    assert login.status_code == 200
    token = login.json()["token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["username"] == "alice"
    assert me.json()["role"] == "user"


def test_disabled_user_cannot_login(client):
    client.post("/api/auth/register", json={"username": "bob", "email": "", "password": "secret123"})
    session = next(client.app.dependency_overrides[get_session]())
    user = session.query(User).filter(User.username == "bob").one()
    user.status = "disabled"
    session.commit()

    response = client.post("/api/auth/login", json={"login": "bob", "password": "secret123"})
    assert response.status_code == 403
    assert response.json()["detail"] == "User disabled"
