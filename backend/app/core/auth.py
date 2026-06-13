from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.models.entities import User
from app.services.auth_service import resolve_token_user

security = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    session: Session = Depends(get_session),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing token")
    user = resolve_token_user(session, credentials.credentials)
    request.state.user_id = user.id
    return user


def verify_admin(user: User = Depends(get_current_user)) -> bool:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin required")
    return True
