from sqlalchemy import inspect

from app.core.database import get_session


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
