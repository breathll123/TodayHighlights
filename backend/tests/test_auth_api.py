from sqlalchemy import inspect

import app.main as main_module
from app.core.database import get_session
from app.models.entities import User
from app.services.auth_service import create_user, verify_password


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


def test_setup_status_requires_bootstrap_for_empty_database(client):
    response = client.get("/api/auth/setup-status")

    assert response.status_code == 200
    assert response.json() == {"setup_required": True}


def test_bootstrap_admin_creates_first_admin_and_closes_setup(client):
    response = client.post(
        "/api/auth/bootstrap-admin",
        json={"username": "owner", "email": "owner@example.com", "password": "secret123"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["role"] == "admin"
    assert client.get("/api/auth/setup-status").json() == {"setup_required": False}

    token = response.json()["token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["username"] == "owner"
    assert me.json()["role"] == "admin"


def test_second_bootstrap_is_rejected(client):
    payload = {"username": "owner", "email": "", "password": "secret123"}
    assert client.post("/api/auth/bootstrap-admin", json=payload).status_code == 200

    response = client.post(
        "/api/auth/bootstrap-admin",
        json={"username": "other", "email": "", "password": "secret456"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Administrator already initialized"


def test_bootstrap_rejects_whitespace_only_username(client):
    response = client.post(
        "/api/auth/bootstrap-admin",
        json={"username": "  ", "email": "", "password": "secret123"},
    )

    assert response.status_code == 422
    assert client.get("/api/auth/setup-status").json() == {"setup_required": True}


def test_public_registration_route_is_removed(client):
    response = client.post(
        "/api/auth/register",
        json={"username": "alice", "email": "", "password": "secret123"},
    )

    assert response.status_code == 404


def test_login_and_me(client):
    bootstrap = client.post(
        "/api/auth/bootstrap-admin",
        json={"username": "alice", "email": "alice@example.com", "password": "secret123"},
    )
    assert bootstrap.status_code == 200

    login = client.post("/api/auth/login", json={"login": "alice", "password": "secret123"})
    assert login.status_code == 200
    token = login.json()["token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["username"] == "alice"
    assert me.json()["role"] == "admin"


def test_disabled_user_cannot_login(client):
    client.post(
        "/api/auth/bootstrap-admin",
        json={"username": "bob", "email": "", "password": "secret123"},
    )
    session = next(client.app.dependency_overrides[get_session]())
    user = session.query(User).filter(User.username == "bob").one()
    user.status = "disabled"
    session.commit()

    response = client.post("/api/auth/login", json={"login": "bob", "password": "secret123"})
    assert response.status_code == 403
    assert response.json()["detail"] == "User disabled"


def test_legacy_default_admin_does_not_close_setup(client):
    session = next(client.app.dependency_overrides[get_session]())
    create_user(session, "admin", "", "admin123", role="admin")
    session.commit()

    response = client.get("/api/auth/setup-status")

    assert response.status_code == 200
    assert response.json() == {"setup_required": True}


def test_bootstrap_replaces_legacy_admin_in_place(client):
    session = next(client.app.dependency_overrides[get_session]())
    legacy = create_user(session, "admin", "", "admin123", role="admin")
    session.commit()
    legacy_id = legacy.id

    response = client.post(
        "/api/auth/bootstrap-admin",
        json={"username": "admin", "email": "owner@example.com", "password": "new-secret"},
    )

    assert response.status_code == 200
    session.expire_all()
    replaced = session.get(User, legacy_id)
    assert replaced is not None
    assert replaced.email == "owner@example.com"
    assert verify_password("new-secret", replaced.password_hash)
    assert not verify_password("admin123", replaced.password_hash)


def test_bootstrap_disables_legacy_admin_when_using_new_username(client):
    session = next(client.app.dependency_overrides[get_session]())
    legacy = create_user(session, "admin", "", "admin123", role="admin")
    session.commit()
    legacy_id = legacy.id

    response = client.post(
        "/api/auth/bootstrap-admin",
        json={"username": "owner", "email": "", "password": "new-secret"},
    )

    assert response.status_code == 200
    session.expire_all()
    replaced = session.get(User, legacy_id)
    assert replaced is not None
    assert replaced.username == f"__legacy_admin_{legacy_id}"
    assert replaced.status == "disabled"
    assert response.json()["user"]["username"] == "owner"


def test_changed_admin_password_is_treated_as_initialized(client):
    session = next(client.app.dependency_overrides[get_session]())
    create_user(session, "admin", "", "changed-secret", role="admin")
    session.commit()

    response = client.get("/api/auth/setup-status")

    assert response.status_code == 200
    assert response.json() == {"setup_required": False}


def test_legacy_admin_login_route_is_removed(client):
    response = client.post("/api/admin/login", json={"password": "admin123"})

    assert response.status_code == 404


def test_application_startup_has_no_database_seed_function():
    assert not hasattr(main_module, "_seed_defaults")
