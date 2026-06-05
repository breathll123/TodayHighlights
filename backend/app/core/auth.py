from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.models.entities import User
from app.services.auth_service import create_token, create_user, resolve_token_user
from app.services.settings import get_plain_setting, set_plain_setting

security = HTTPBearer(auto_error=False)
DEFAULT_PASSWORD = "admin123"


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    session: Session = Depends(get_session),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing token")
    return resolve_token_user(session, credentials.credentials)


def verify_admin(user: User = Depends(get_current_user)) -> bool:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin required")
    return True


def create_admin_token(password: str, session: Session) -> str:
    stored = get_plain_setting(session, "admin.password", DEFAULT_PASSWORD)
    if password != stored:
        raise HTTPException(status_code=403, detail="Incorrect password")
    admin = session.query(User).filter(User.role == "admin").first()
    if admin is None:
        admin = create_user(session, "admin", "", password, role="admin")
    return create_token(admin)


def seed_default_password(session: Session) -> None:
    existing = get_plain_setting(session, "admin.password")
    if not existing:
        set_plain_setting(session, "admin.password", DEFAULT_PASSWORD)
    admin = session.query(User).filter(User.role == "admin").first()
    if admin is None:
        create_user(session, "admin", "", existing or DEFAULT_PASSWORD, role="admin")
    session.commit()
