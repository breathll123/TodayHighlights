import json
import time

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import CryptoService
from app.core.database import get_session
from app.services.settings import get_plain_setting, set_plain_setting

security = HTTPBearer(auto_error=False)
DEFAULT_PASSWORD = "admin123"


def verify_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    session: Session = Depends(get_session),
) -> bool:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing token")

    try:
        crypto = CryptoService(settings.app_secret_key)
        payload = json.loads(crypto.decrypt(credentials.credentials))
        exp = payload.get("exp", 0)
        if exp < time.time():
            raise HTTPException(status_code=401, detail="Token expired")
        return True
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


def create_admin_token(password: str, session: Session) -> str:
    stored = get_plain_setting(session, "admin.password", DEFAULT_PASSWORD)
    if password != stored:
        raise HTTPException(status_code=403, detail="Incorrect password")

    crypto = CryptoService(settings.app_secret_key)
    payload = json.dumps({"exp": int(time.time()) + 86400 * 7})  # 7 days
    return crypto.encrypt(payload)


def seed_default_password(session: Session) -> None:
    existing = get_plain_setting(session, "admin.password")
    if not existing:
        set_plain_setting(session, "admin.password", DEFAULT_PASSWORD)
        session.commit()
