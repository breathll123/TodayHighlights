from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_session
from app.models.entities import User
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, SetupStatusResponse, UserRead
from app.services.admin_bootstrap import bootstrap_admin, setup_required
from app.services.auth_service import authenticate_user, create_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _read_user(user: User) -> UserRead:
    return UserRead(id=user.id, username=user.username, email=user.email, role=user.role, status=user.status)


@router.get("/setup-status", response_model=SetupStatusResponse)
def get_setup_status(session: Session = Depends(get_session)) -> SetupStatusResponse:
    return SetupStatusResponse(setup_required=setup_required(session))


@router.post("/bootstrap-admin", response_model=AuthResponse)
def create_first_admin(
    payload: RegisterRequest,
    session: Session = Depends(get_session),
) -> AuthResponse:
    user = bootstrap_admin(
        session,
        payload.username.strip(),
        payload.email.strip(),
        payload.password,
    )
    return AuthResponse(token=create_token(user), user=_read_user(user))


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, session: Session = Depends(get_session)) -> AuthResponse:
    user = authenticate_user(session, payload.login.strip(), payload.password)
    token = create_token(user)
    session.commit()
    return AuthResponse(token=token, user=_read_user(user))


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)) -> UserRead:
    return _read_user(user)
