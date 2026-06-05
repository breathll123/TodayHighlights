import hashlib
import json
import secrets
import time
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import CryptoService
from app.models.entities import User

TOKEN_TTL_SECONDS = 86400 * 7


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 210_000).hex()
    return f"pbkdf2_sha256${salt}${digest}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        method, salt, digest = password_hash.split("$", 2)
    except ValueError:
        return False
    if method != "pbkdf2_sha256":
        return False
    expected = hash_password(password, salt).split("$", 2)[2]
    return secrets.compare_digest(expected, digest)


def create_user(session: Session, username: str, email: str, password: str, role: str = "user") -> User:
    existing = session.scalar(
        select(User).where(or_(User.username == username, User.email == email) if email else User.username == username)
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="User already exists")
    user = User(username=username, email=email or None, password_hash=hash_password(password), role=role, status="active")
    session.add(user)
    session.flush()
    return user


def create_token(user: User) -> str:
    crypto = CryptoService(settings.app_secret_key)
    payload = json.dumps({"user_id": user.id, "role": user.role, "exp": int(time.time()) + TOKEN_TTL_SECONDS})
    return crypto.encrypt(payload)


def authenticate_user(session: Session, login: str, password: str) -> User:
    user = session.scalar(select(User).where(or_(User.username == login, User.email == login)))
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=403, detail="Incorrect credentials")
    if user.status != "active":
        raise HTTPException(status_code=403, detail="User disabled")
    user.last_login_at = datetime.utcnow()
    session.flush()
    return user


def resolve_token_user(session: Session, token: str) -> User:
    try:
        crypto = CryptoService(settings.app_secret_key)
        payload = json.loads(crypto.decrypt(token))
        if payload.get("exp", 0) < time.time():
            raise HTTPException(status_code=401, detail="Token expired")
        user_id = int(payload["user_id"])
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    if user.status != "active":
        raise HTTPException(status_code=403, detail="User disabled")
    return user
