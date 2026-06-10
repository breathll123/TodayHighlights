from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.entities import AppSetting, User
from app.services.auth_service import create_user, hash_password, verify_password
from app.services.settings import get_plain_setting

BOOTSTRAP_COMPLETED_KEY = "system.admin_bootstrap_completed"
LEGACY_PASSWORD_KEY = "admin.password"
LEGACY_USERNAME = "admin"
LEGACY_PASSWORD = "admin123"


def is_legacy_default_admin(session: Session, user: User) -> bool:
    stored = get_plain_setting(session, LEGACY_PASSWORD_KEY)
    return (
        user.username == LEGACY_USERNAME
        and user.role == "admin"
        and (not stored or stored == LEGACY_PASSWORD)
        and verify_password(LEGACY_PASSWORD, user.password_hash)
    )


def setup_required(session: Session) -> bool:
    if session.get(AppSetting, BOOTSTRAP_COMPLETED_KEY) is not None:
        return False

    admins = session.scalars(
        select(User).where(User.role == "admin", User.status == "active")
    ).all()
    return not any(not is_legacy_default_admin(session, user) for user in admins)


def bootstrap_admin(
    session: Session,
    username: str,
    email: str,
    password: str,
) -> User:
    if not setup_required(session):
        raise HTTPException(
            status_code=409,
            detail="Administrator already initialized",
        )

    session.add(
        AppSetting(
            key=BOOTSTRAP_COMPLETED_KEY,
            value_json={"value": "true"},
            value_encrypted="",
        )
    )
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Administrator already initialized",
        ) from exc

    legacy = session.scalar(
        select(User).where(
            User.username == LEGACY_USERNAME,
            User.role == "admin",
        )
    )
    if legacy is not None and is_legacy_default_admin(session, legacy):
        if username == LEGACY_USERNAME:
            legacy.email = email or None
            legacy.password_hash = hash_password(password)
            legacy.role = "admin"
            legacy.status = "active"
            admin = legacy
        else:
            legacy.username = f"__legacy_admin_{legacy.id}"
            legacy.status = "disabled"
            admin = create_user(session, username, email, password, role="admin")
    else:
        admin = create_user(session, username, email, password, role="admin")

    legacy_setting = session.get(AppSetting, LEGACY_PASSWORD_KEY)
    if legacy_setting is not None:
        session.delete(legacy_setting)

    session.commit()
    session.refresh(admin)
    return admin
