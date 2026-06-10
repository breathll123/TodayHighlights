# Block AI Analysis Auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add login-gated block-level AI analysis with user roles, token usage tracking, and an AI drawer on public topic pages.

**Architecture:** Keep the existing modular monolith. Add normal users and admin roles in the backend, then add block analysis as a separate AI service that reuses current page block resolution and AI model configuration. The frontend keeps public pages browsable, but gates AI analysis behind auth and renders results in a right drawer or mobile bottom sheet.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, MySQL-compatible migrations, Pydantic, React, Vite, TanStack Query, Tailwind, shadcn-style local UI components, Vitest.

---

## Scope Check

The approved spec covers two tightly related subsystems:

- user auth and role enforcement, required before public users can trigger AI;
- block-level AI analysis and token usage tracking, which depends on authenticated users.

This can be implemented as one plan because the AI feature cannot be tested correctly without the auth model. Top market trend charts are out of scope.

## File Structure

### Backend

- Modify `backend/app/models/entities.py`
  - Add `User`, `AIBlockAnalysis`, `AITokenUsage`.
  - Extend `AIGenerationJob` with `user_id` and `block_analysis_id`.
- Create `backend/migrations/versions/20260605_0007_block_ai_analysis_auth.py`
  - Add new tables and nullable job links.
  - Leave default admin creation to the existing startup seed flow.
- Modify `backend/app/core/auth.py`
  - Replace admin-password-only token validation with user token validation.
  - Keep admin verification as role-specific dependency.
- Create `backend/app/schemas/auth.py`
  - Register, login, and current-user schemas.
- Create `backend/app/schemas/ai_block_analysis.py`
  - Public block analysis response and admin usage schemas.
- Create `backend/app/services/auth_service.py`
  - Password hashing, user creation, login, token creation, current user resolution.
- Create `backend/app/services/token_usage.py`
  - Usage extraction and rough token estimation.
- Modify `backend/app/services/ai_client.py`
  - Return AI JSON content plus provider token usage.
- Create `backend/app/services/ai_block_analysis.py`
  - Resolve block data, hash data, prompt model, validate output, cache generated analysis.
- Modify `backend/app/api/admin.py`
  - Update login compatibility.
  - Add admin user and token usage endpoints.
  - Add admin regenerate endpoint.
- Create `backend/app/api/auth.py`
  - Public register/login/me endpoints.
- Create `backend/app/api/ai.py`
  - Login-required block analysis endpoints.
- Modify `backend/app/main.py`
  - Include new auth and AI routers.
- Create tests:
  - `backend/tests/test_auth_api.py`
  - `backend/tests/test_ai_block_analysis.py`
  - `backend/tests/test_admin_users_usage.py`

### Frontend

- Modify `frontend/src/hooks/use-auth.tsx`
  - Replace admin-only auth state with user auth state and role.
- Modify `frontend/src/App.tsx`
  - Route admin layout by `role=admin`; keep public routes open.
- Modify `frontend/src/api/types.ts`
  - Add auth, block analysis, user, and usage types.
- Modify `frontend/src/api/client.ts`
  - Add auth, block analysis, admin users, token usage API calls.
- Modify `frontend/src/pages/LoginPage.tsx`
  - Support login/register and return URL.
- Modify `frontend/src/components/layout/SectionHeading.tsx`
  - Accept an action slot.
- Modify `frontend/src/components/layout/GridRenderer.tsx`
  - Add AI button per block and own the drawer state.
- Create `frontend/src/components/layout/BlockAIAnalysisDrawer.tsx`
  - Drawer/sheet UI, cache/generate states, evidence accordion.
- Create `frontend/src/pages/AdminUsersPage.tsx`
  - Admin user management.
- Create `frontend/src/pages/AdminAIUsagePage.tsx`
  - Admin token usage table.
- Modify `frontend/src/components/admin/AdminSidebar.tsx`
  - Add users and AI usage nav items.
- Create or extend tests:
  - `frontend/src/__tests__/auth.test.tsx`
  - `frontend/src/__tests__/block-ai-analysis.test.tsx`
  - `frontend/src/__tests__/admin-users-usage.test.tsx`

---

## Task 1: Backend Models And Migration

**Files:**
- Modify: `backend/app/models/entities.py`
- Create: `backend/migrations/versions/20260605_0007_block_ai_analysis_auth.py`
- Test: `backend/tests/test_auth_api.py`
- Test: `backend/tests/test_ai_block_analysis.py`

- [ ] **Step 1: Write failing model-column tests**

Create `backend/tests/test_auth_api.py` with the model metadata assertions first:

```python
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
```

Create `backend/tests/test_ai_block_analysis.py` with table shape assertions:

```python
from sqlalchemy import inspect

from app.core.database import get_session


def test_ai_block_analysis_tables_exist(client):
    session = next(client.app.dependency_overrides[get_session]())
    inspector = inspect(session.bind)
    block_columns = {col["name"] for col in inspector.get_columns("ai_block_analyses")}
    usage_columns = {col["name"] for col in inspector.get_columns("ai_token_usages")}
    job_columns = {col["name"] for col in inspector.get_columns("ai_generation_jobs")}

    assert {
        "page_route",
        "block_id",
        "block_title",
        "source_type",
        "data_hash",
        "status",
        "summary_points_json",
        "key_changes_json",
        "risk_points_json",
        "related_entities_json",
        "evidence_refs_json",
        "generated_by_user_id",
        "token_usage_id",
        "expires_at",
    }.issubset(block_columns)
    assert {
        "user_id",
        "model_config_id",
        "model_name",
        "usage_type",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "estimated",
        "request_status",
        "related_job_id",
        "related_block_analysis_id",
    }.issubset(usage_columns)
    assert {"user_id", "block_analysis_id"}.issubset(job_columns)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
pytest tests/test_auth_api.py::test_users_table_columns_exist tests/test_ai_block_analysis.py::test_ai_block_analysis_tables_exist -q
```

Expected: both tests fail because `users`, `ai_block_analyses`, and `ai_token_usages` do not exist.

- [ ] **Step 3: Add SQLAlchemy entities**

In `backend/app/models/entities.py`, add these relationships and classes. Add `users` relationships after `Topic` relationships are already defined, and add new classes before `AppSetting`:

```python
class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("username", name="uq_users_username"),
        UniqueConstraint("email", name="uq_users_email"),
        Index("ix_users_role_status", "role", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), nullable=False)
    email: Mapped[str | None] = mapped_column(String(160), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)
```

```python
class AIBlockAnalysis(TimestampMixin, Base):
    __tablename__ = "ai_block_analyses"
    __table_args__ = (
        Index("ix_ai_block_analysis_cache", "page_route", "block_id", "data_hash", "status", "expires_at"),
        Index("ix_ai_block_analysis_user_created", "generated_by_user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    page_route: Mapped[str] = mapped_column(String(80), nullable=False)
    block_id: Mapped[int] = mapped_column(ForeignKey("page_blocks.id"), nullable=False)
    block_title: Mapped[str] = mapped_column(String(120), nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    data_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="processing", nullable=False)
    summary_points_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    key_changes_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    risk_points_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    related_entities_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    evidence_refs_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    model_config_id: Mapped[int | None] = mapped_column(ForeignKey("ai_model_configs.id"))
    generated_by_model: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    generated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    token_usage_id: Mapped[int | None] = mapped_column(ForeignKey("ai_token_usages.id"))
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
```

```python
class AITokenUsage(Base):
    __tablename__ = "ai_token_usages"
    __table_args__ = (
        Index("ix_ai_token_usages_user_created", "user_id", "created_at"),
        Index("ix_ai_token_usages_model_created", "model_config_id", "created_at"),
        Index("ix_ai_token_usages_type_created", "usage_type", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    model_config_id: Mapped[int | None] = mapped_column(ForeignKey("ai_model_configs.id"))
    model_name: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    usage_type: Mapped[str] = mapped_column(String(40), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    request_status: Mapped[str] = mapped_column(String(30), default="success", nullable=False)
    related_job_id: Mapped[int | None] = mapped_column(ForeignKey("ai_generation_jobs.id"))
    related_block_analysis_id: Mapped[int | None] = mapped_column(ForeignKey("ai_block_analyses.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
```

Extend `AIGenerationJob` with:

```python
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    block_analysis_id: Mapped[int | None] = mapped_column(ForeignKey("ai_block_analyses.id"))
```

- [ ] **Step 4: Add Alembic migration**

Create `backend/migrations/versions/20260605_0007_block_ai_analysis_auth.py`:

```python
"""block ai analysis auth

Revision ID: 20260605_0007
Revises: 20260605_0006
Create Date: 2026-06-05
"""

from alembic import op
import sqlalchemy as sa


revision = "20260605_0007"
down_revision = "20260605_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("email", sa.String(length=160), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("username", name="uq_users_username"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_role_status", "users", ["role", "status"])

    op.create_table(
        "ai_block_analyses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("page_route", sa.String(length=80), nullable=False),
        sa.Column("block_id", sa.Integer(), sa.ForeignKey("page_blocks.id"), nullable=False),
        sa.Column("block_title", sa.String(length=120), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("data_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="processing"),
        sa.Column("summary_points_json", sa.JSON(), nullable=False),
        sa.Column("key_changes_json", sa.JSON(), nullable=False),
        sa.Column("risk_points_json", sa.JSON(), nullable=False),
        sa.Column("related_entities_json", sa.JSON(), nullable=False),
        sa.Column("evidence_refs_json", sa.JSON(), nullable=False),
        sa.Column("model_config_id", sa.Integer(), sa.ForeignKey("ai_model_configs.id"), nullable=True),
        sa.Column("generated_by_model", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("generated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("token_usage_id", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("generated_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_ai_block_analysis_cache",
        "ai_block_analyses",
        ["page_route", "block_id", "data_hash", "status", "expires_at"],
    )
    op.create_index(
        "ix_ai_block_analysis_user_created",
        "ai_block_analyses",
        ["generated_by_user_id", "created_at"],
    )

    op.create_table(
        "ai_token_usages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("model_config_id", sa.Integer(), sa.ForeignKey("ai_model_configs.id"), nullable=True),
        sa.Column("model_name", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("usage_type", sa.String(length=40), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("request_status", sa.String(length=30), nullable=False, server_default="success"),
        sa.Column("related_job_id", sa.Integer(), sa.ForeignKey("ai_generation_jobs.id"), nullable=True),
        sa.Column("related_block_analysis_id", sa.Integer(), sa.ForeignKey("ai_block_analyses.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ai_token_usages_user_created", "ai_token_usages", ["user_id", "created_at"])
    op.create_index("ix_ai_token_usages_model_created", "ai_token_usages", ["model_config_id", "created_at"])
    op.create_index("ix_ai_token_usages_type_created", "ai_token_usages", ["usage_type", "created_at"])

    op.create_foreign_key(
        "fk_ai_block_analyses_token_usage",
        "ai_block_analyses",
        "ai_token_usages",
        ["token_usage_id"],
        ["id"],
    )
    op.add_column("ai_generation_jobs", sa.Column("user_id", sa.Integer(), nullable=True))
    op.add_column("ai_generation_jobs", sa.Column("block_analysis_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_ai_generation_jobs_user", "ai_generation_jobs", "users", ["user_id"], ["id"])
    op.create_foreign_key(
        "fk_ai_generation_jobs_block_analysis",
        "ai_generation_jobs",
        "ai_block_analyses",
        ["block_analysis_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_ai_generation_jobs_block_analysis", "ai_generation_jobs", type_="foreignkey")
    op.drop_constraint("fk_ai_generation_jobs_user", "ai_generation_jobs", type_="foreignkey")
    op.drop_column("ai_generation_jobs", "block_analysis_id")
    op.drop_column("ai_generation_jobs", "user_id")
    op.drop_constraint("fk_ai_block_analyses_token_usage", "ai_block_analyses", type_="foreignkey")
    op.drop_table("ai_token_usages")
    op.drop_table("ai_block_analyses")
    op.drop_table("users")
```

- [ ] **Step 5: Run model tests**

Run:

```bash
cd backend
pytest tests/test_auth_api.py::test_users_table_columns_exist tests/test_ai_block_analysis.py::test_ai_block_analysis_tables_exist -q
```

Expected: both tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/entities.py backend/migrations/versions/20260605_0007_block_ai_analysis_auth.py backend/tests/test_auth_api.py backend/tests/test_ai_block_analysis.py
git commit -m "feat(auth): add user and block ai tables"
```

---

## Task 2: User Auth Service And API

**Files:**
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/services/auth_service.py`
- Modify: `backend/app/core/auth.py`
- Create: `backend/app/api/auth.py`
- Modify: `backend/app/api/admin.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_auth_api.py`

- [ ] **Step 1: Add failing auth API tests**

Append to `backend/tests/test_auth_api.py`:

```python
from app.core.database import get_session
from app.models.entities import User


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
```

- [ ] **Step 2: Run auth API tests to verify failure**

Run:

```bash
cd backend
pytest tests/test_auth_api.py::test_register_login_and_me tests/test_auth_api.py::test_disabled_user_cannot_login -q
```

Expected: fail with 404 for `/api/auth/register`.

- [ ] **Step 3: Add auth schemas**

Create `backend/app/schemas/auth.py`:

```python
from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=80)
    email: str = Field(default="", max_length=160)
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    login: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=6, max_length=128)


class UserRead(BaseModel):
    id: int
    username: str
    email: str | None
    role: str
    status: str


class AuthResponse(BaseModel):
    token: str
    user: UserRead
```

- [ ] **Step 4: Add auth service**

Create `backend/app/services/auth_service.py`:

```python
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
```

- [ ] **Step 5: Update auth dependencies**

Replace `backend/app/core/auth.py` with:

```python
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
```

- [ ] **Step 6: Add auth router**

Create `backend/app/api/auth.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_session
from app.models.entities import User
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserRead
from app.services.auth_service import authenticate_user, create_token, create_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _read_user(user: User) -> UserRead:
    return UserRead(id=user.id, username=user.username, email=user.email, role=user.role, status=user.status)


@router.post("/register", response_model=AuthResponse)
def register(payload: RegisterRequest, session: Session = Depends(get_session)) -> AuthResponse:
    user = create_user(session, payload.username.strip(), payload.email.strip(), payload.password)
    token = create_token(user)
    session.commit()
    return AuthResponse(token=token, user=_read_user(user))


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, session: Session = Depends(get_session)) -> AuthResponse:
    user = authenticate_user(session, payload.login.strip(), payload.password)
    token = create_token(user)
    session.commit()
    return AuthResponse(token=token, user=_read_user(user))


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)) -> UserRead:
    return _read_user(user)
```

In `backend/app/main.py`, import and include:

```python
from app.api import admin, public, auth
```

At router setup, add before admin router:

```python
app.include_router(auth.router)
```

Keep `app.include_router(admin.auth_router)` for compatibility.

- [ ] **Step 7: Run auth tests**

Run:

```bash
cd backend
pytest tests/test_auth_api.py -q
```

Expected: all tests in `test_auth_api.py` pass.

- [ ] **Step 8: Commit**

```bash
git add backend/app/core/auth.py backend/app/api/auth.py backend/app/main.py backend/app/schemas/auth.py backend/app/services/auth_service.py backend/tests/test_auth_api.py
git commit -m "feat(auth): add user registration and role auth"
```

---

## Task 3: AI Client Usage And Token Accounting

**Files:**
- Modify: `backend/app/services/ai_client.py`
- Create: `backend/app/services/token_usage.py`
- Modify: `backend/app/services/ai_enrichment.py`
- Test: `backend/tests/test_ai_block_analysis.py`
- Test: `backend/tests/test_jobs_ai_integration.py`

- [ ] **Step 1: Add failing token usage unit tests**

Append to `backend/tests/test_ai_block_analysis.py`:

```python
import pytest

from app.services.ai_client import AIClient
from app.services.token_usage import estimate_tokens, extract_token_usage


def test_ai_client_returns_json_and_usage():
    async def fake_post(payload):
        return {
            "choices": [{"message": {"content": "{\"summary_points\":[\"A\"]}"}}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
        }

    import asyncio

    client = AIClient("https://example.com", "key", "model-a", post_json=fake_post)
    result = asyncio.run(client.complete_json_with_usage("system", "user"))

    assert result.content == {"summary_points": ["A"]}
    assert result.usage == {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18}
    assert result.usage_estimated is False


def test_usage_estimation_when_provider_does_not_return_usage():
    usage = extract_token_usage({}, "abcd" * 100, "{\"a\":1}")
    assert usage["total_tokens"] > 0
    assert usage["estimated"] is True


def test_estimate_tokens_is_stable_for_short_text():
    assert estimate_tokens("abcdefgh") == 2
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd backend
pytest tests/test_ai_block_analysis.py::test_ai_client_returns_json_and_usage tests/test_ai_block_analysis.py::test_usage_estimation_when_provider_does_not_return_usage tests/test_ai_block_analysis.py::test_estimate_tokens_is_stable_for_short_text -q
```

Expected: fail because `complete_json_with_usage` and `token_usage.py` do not exist.

- [ ] **Step 3: Add token usage helper**

Create `backend/app/services/token_usage.py`:

```python
def estimate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4)


def extract_token_usage(response: dict, prompt_text: str, completion_text: str) -> dict:
    usage = response.get("usage") or {}
    prompt = usage.get("prompt_tokens")
    completion = usage.get("completion_tokens")
    total = usage.get("total_tokens")
    if isinstance(prompt, int) and isinstance(completion, int) and isinstance(total, int):
        return {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": total,
            "estimated": False,
        }
    prompt_estimate = estimate_tokens(prompt_text)
    completion_estimate = estimate_tokens(completion_text)
    return {
        "prompt_tokens": prompt_estimate,
        "completion_tokens": completion_estimate,
        "total_tokens": prompt_estimate + completion_estimate,
        "estimated": True,
    }
```

- [ ] **Step 4: Update AI client**

Modify `backend/app/services/ai_client.py`:

```python
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx

from app.services.token_usage import extract_token_usage

PostJson = Callable[[dict], Awaitable[dict]]


@dataclass(frozen=True)
class AIJSONResult:
    content: dict
    usage: dict
    usage_estimated: bool


class AIClient:
    def __init__(self, base_url: str, api_key: str, model: str, post_json: PostJson | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self._post_json = post_json

    async def complete_json(self, system_prompt: str, user_prompt: str) -> dict:
        result = await self.complete_json_with_usage(system_prompt, user_prompt)
        return result.content

    async def complete_json_with_usage(self, system_prompt: str, user_prompt: str) -> AIJSONResult:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        response = await self._send(payload)
        content_text = response["choices"][0]["message"]["content"]
        usage = extract_token_usage(response, f"{system_prompt}\n{user_prompt}", content_text)
        return AIJSONResult(
            content=json.loads(content_text),
            usage={
                "prompt_tokens": usage["prompt_tokens"],
                "completion_tokens": usage["completion_tokens"],
                "total_tokens": usage["total_tokens"],
            },
            usage_estimated=usage["estimated"],
        )

    async def _send(self, payload: dict) -> dict:
        if self._post_json is not None:
            return await self._post_json(payload)
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            response.raise_for_status()
            return response.json()
```

- [ ] **Step 5: Run token tests**

Run:

```bash
cd backend
pytest tests/test_ai_block_analysis.py::test_ai_client_returns_json_and_usage tests/test_ai_block_analysis.py::test_usage_estimation_when_provider_does_not_return_usage tests/test_ai_block_analysis.py::test_estimate_tokens_is_stable_for_short_text -q
```

Expected: pass.

- [ ] **Step 6: Run existing AI integration tests**

Run:

```bash
cd backend
pytest tests/test_ai_enrichment.py tests/test_jobs_ai_integration.py tests/test_ai_admin_api.py -q
```

Expected: pass. This confirms `complete_json()` compatibility still works for existing AI enrichment.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/ai_client.py backend/app/services/token_usage.py backend/tests/test_ai_block_analysis.py
git commit -m "feat(ai): capture model token usage"
```

---

## Task 4: Block Analysis Service

**Files:**
- Create: `backend/app/schemas/ai_block_analysis.py`
- Create: `backend/app/services/ai_block_analysis.py`
- Modify: `backend/app/services/ai_enrichment.py`
- Test: `backend/tests/test_ai_block_analysis.py`

- [ ] **Step 1: Add failing service tests**

Append to `backend/tests/test_ai_block_analysis.py`:

```python
from datetime import datetime, timedelta

from app.core.database import get_session
from app.core.config import settings
from app.core.crypto import CryptoService
from app.models.entities import AIBlockAnalysis, AIModelConfig, PageBlock, Topic, User
from app.services.ai_block_analysis import analyze_block, build_block_data_hash, validate_block_analysis_payload


def _seed_user_model_block(session):
    user = User(username="alice", email="", password_hash="hash", role="user", status="active")
    topic = Topic(name="股票", slug="stocks", enabled=True)
    session.add_all([user, topic])
    session.flush()
    block = PageBlock(
        page_route="/topics/stocks",
        title="热门资讯",
        source_type="topic",
        source_config={"topic_id": topic.id},
        display_count=5,
        sort_order=1,
        enabled=True,
        status="published",
    )
    key = CryptoService(settings.app_secret_key).encrypt("api-key")
    model = AIModelConfig(name="Default", base_url="https://example.com", model="free-model", api_key_encrypted=key, is_default=True, enabled=True)
    session.add_all([block, model])
    session.commit()
    return user, block


def test_validate_block_analysis_payload_bounds():
    payload = validate_block_analysis_payload(
        {
            "summary_points": ["核心内容"],
            "key_changes": ["变化"],
            "risk_points": ["风险"],
            "related_entities": ["A股"],
            "confidence": 0.7,
        }
    )
    assert payload.summary_points == ["核心内容"]
    assert payload.confidence == 0.7


def test_build_block_data_hash_is_stable():
    data = [{"title": "A", "summary": "B"}, {"summary": "D", "title": "C"}]
    assert build_block_data_hash(data) == build_block_data_hash(list(data))


def test_analyze_block_generates_and_records_token_usage(client):
    session = next(client.app.dependency_overrides[get_session]())
    user, block = _seed_user_model_block(session)

    async def fake_post(payload):
        return {
            "choices": [{"message": {"content": "{\"summary_points\":[\"多条内容集中在AI算力\"],\"key_changes\":[],\"risk_points\":[],\"related_entities\":[\"AI\"],\"confidence\":0.8}"}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
        }

    analysis = analyze_block(
        session,
        user=user,
        page_route="/topics/stocks",
        block_id=block.id,
        post_json=fake_post,
        resolved_data=[{"id": 1, "title": "AI算力走强", "summary": "相关公司活跃", "source": "测试源"}],
    )
    session.commit()

    assert analysis.status == "generated"
    assert analysis.summary_points_json == ["多条内容集中在AI算力"]
    assert analysis.token_usage_id is not None
    assert analysis.generated_by_user_id == user.id


def test_analyze_block_uses_valid_cache(client):
    session = next(client.app.dependency_overrides[get_session]())
    user, block = _seed_user_model_block(session)
    data = [{"id": 1, "title": "缓存内容", "summary": "不应调用模型"}]
    cached = AIBlockAnalysis(
        page_route="/topics/stocks",
        block_id=block.id,
        block_title=block.title,
        source_type=block.source_type,
        data_hash=build_block_data_hash(data),
        status="generated",
        summary_points_json=["缓存结果"],
        expires_at=datetime.utcnow() + timedelta(minutes=30),
    )
    session.add(cached)
    session.commit()

    async def fake_post(payload):
        raise AssertionError("cache hit should not call model")

    analysis = analyze_block(
        session,
        user=user,
        page_route="/topics/stocks",
        block_id=block.id,
        post_json=fake_post,
        resolved_data=data,
    )
    assert analysis.id == cached.id
    assert analysis.summary_points_json == ["缓存结果"]
```

- [ ] **Step 2: Run service tests to verify failure**

Run:

```bash
cd backend
pytest tests/test_ai_block_analysis.py::test_validate_block_analysis_payload_bounds tests/test_ai_block_analysis.py::test_build_block_data_hash_is_stable tests/test_ai_block_analysis.py::test_analyze_block_generates_and_records_token_usage tests/test_ai_block_analysis.py::test_analyze_block_uses_valid_cache -q
```

Expected: fail because `app.services.ai_block_analysis` does not exist.

- [ ] **Step 3: Add block analysis schemas**

Create `backend/app/schemas/ai_block_analysis.py`:

```python
from datetime import datetime

from pydantic import BaseModel


class BlockAnalysisValidated(BaseModel):
    summary_points: list[str]
    key_changes: list[str]
    risk_points: list[str]
    related_entities: list[str]
    confidence: float


class BlockAnalysisEvidenceRead(BaseModel):
    title: str
    source: str = ""
    published_at: str | None = None
    url: str | None = None


class BlockAnalysisRead(BaseModel):
    id: int
    page_route: str
    block_id: int
    block_title: str
    status: str
    summary_points: list[str]
    key_changes: list[str]
    risk_points: list[str]
    related_entities: list[str]
    evidence_refs: list[BlockAnalysisEvidenceRead]
    generated_by_model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    token_estimated: bool = False
    generated_at: datetime | None = None
    expires_at: datetime | None = None
```

- [ ] **Step 4: Add block analysis service**

Create `backend/app/services/ai_block_analysis.py`:

```python
import asyncio
import json
from datetime import datetime, timedelta
from hashlib import sha256

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import CryptoService
from app.models.entities import AIGenerationJob, AIBlockAnalysis, AIModelConfig, AITokenUsage, PageBlock, User
from app.schemas.ai_block_analysis import BlockAnalysisValidated
from app.services.ai_client import AIClient, PostJson
from app.services.ai_models import get_default_ai_model
from app.services.blocks import resolve_block_data

BLOCK_ANALYSIS_TTL_MINUTES = 60
BLOCK_ANALYSIS_SYSTEM_PROMPT = (
    "你是今日看点的区块级信息分析助手。只基于用户提供的方块内容分析，不能补充外部事实。"
    "输出 JSON：summary_points, key_changes, risk_points, related_entities, confidence。"
    "summary_points 根据复杂度输出 1-4 条。股票类不得给买入、卖出、持有建议。"
)


def _trim_list(values: object, max_items: int, max_chars: int) -> list[str]:
    if not isinstance(values, list):
        return []
    result: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        text = value.strip()
        if text:
            result.append(text[:max_chars])
        if len(result) >= max_items:
            break
    return result


def validate_block_analysis_payload(payload: dict) -> BlockAnalysisValidated:
    summary_points = _trim_list(payload.get("summary_points"), 4, 160)
    if not summary_points:
        raise ValueError("summary_points is required")
    confidence = payload.get("confidence", 0)
    if not isinstance(confidence, int | float):
        raise ValueError("confidence must be a number")
    confidence = max(0.0, min(1.0, float(confidence)))
    return BlockAnalysisValidated(
        summary_points=summary_points,
        key_changes=_trim_list(payload.get("key_changes"), 3, 140),
        risk_points=_trim_list(payload.get("risk_points"), 2, 140),
        related_entities=_trim_list(payload.get("related_entities"), 8, 40),
        confidence=confidence,
    )


def build_block_data_hash(data: list[dict]) -> str:
    normalized = json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)
    return sha256(normalized.encode()).hexdigest()


def build_evidence_refs(data: list[dict]) -> list[dict]:
    refs: list[dict] = []
    for item in data[:12]:
        refs.append(
            {
                "title": str(item.get("title") or item.get("name") or "")[:160],
                "source": str(item.get("source") or item.get("source_type") or "")[:80],
                "published_at": item.get("published_at") or item.get("created_at") or item.get("time"),
                "url": item.get("url"),
            }
        )
    return refs


def block_user_prompt(block: PageBlock, data: list[dict]) -> str:
    compact = [
        {
            "title": item.get("title") or item.get("name"),
            "summary": item.get("summary") or item.get("content"),
            "tags": item.get("tags") or item.get("tags_json"),
            "metrics": item.get("metrics") or {k: item.get(k) for k in ("score", "percent", "rank", "status")},
        }
        for item in data[:20]
    ]
    return json.dumps(
        {"block_title": block.title, "source_type": block.source_type, "items": compact},
        ensure_ascii=False,
    )


def find_cached_analysis(session: Session, page_route: str, block_id: int, data_hash: str) -> AIBlockAnalysis | None:
    now = datetime.utcnow()
    return session.scalar(
        select(AIBlockAnalysis)
        .where(
            AIBlockAnalysis.page_route == page_route,
            AIBlockAnalysis.block_id == block_id,
            AIBlockAnalysis.data_hash == data_hash,
            AIBlockAnalysis.status == "generated",
            AIBlockAnalysis.expires_at > now,
        )
        .order_by(AIBlockAnalysis.generated_at.desc())
        .limit(1)
    )


def analyze_block(
    session: Session,
    *,
    user: User,
    page_route: str,
    block_id: int,
    post_json: PostJson | None = None,
    force: bool = False,
    resolved_data: list[dict] | None = None,
) -> AIBlockAnalysis:
    block = session.get(PageBlock, block_id)
    if block is None or block.page_route != page_route or not block.enabled or block.status != "published":
        raise HTTPException(status_code=404, detail="Block not found")
    data = resolved_data if resolved_data is not None else resolve_block_data(session, block)
    data_hash = build_block_data_hash(data)
    if not force:
        cached = find_cached_analysis(session, page_route, block_id, data_hash)
        if cached is not None:
            return cached

    model_cfg = get_default_ai_model(session)
    if model_cfg is None:
        raise HTTPException(status_code=400, detail="No default AI model configured")

    analysis = AIBlockAnalysis(
        page_route=page_route,
        block_id=block.id,
        block_title=block.title,
        source_type=block.source_type,
        data_hash=data_hash,
        status="processing",
        generated_by_user_id=user.id,
        model_config_id=model_cfg.id,
        expires_at=datetime.utcnow() + timedelta(minutes=BLOCK_ANALYSIS_TTL_MINUTES),
    )
    session.add(analysis)
    session.flush()

    job = AIGenerationJob(
        job_type="block_analysis",
        trigger_type="manual" if not force else "regenerate",
        status="processing",
        user_id=user.id,
        block_analysis_id=analysis.id,
        model_config_id=model_cfg.id,
        input_count=len(data),
        started_at=datetime.utcnow(),
    )
    session.add(job)
    session.flush()

    try:
        crypto = CryptoService(settings.app_secret_key)
        client = AIClient(model_cfg.base_url, crypto.decrypt(model_cfg.api_key_encrypted), model_cfg.model, post_json=post_json)
        prompt = block_user_prompt(block, data)
        result = asyncio.run(client.complete_json_with_usage(BLOCK_ANALYSIS_SYSTEM_PROMPT, prompt))
        validated = validate_block_analysis_payload(result.content)

        analysis.summary_points_json = validated.summary_points
        analysis.key_changes_json = validated.key_changes
        analysis.risk_points_json = validated.risk_points
        analysis.related_entities_json = validated.related_entities
        analysis.evidence_refs_json = build_evidence_refs(data)
        analysis.generated_by_model = model_cfg.model
        analysis.generated_at = datetime.utcnow()
        analysis.status = "generated"
        job.status = "succeeded"
        job.success_count = 1
        job.finished_at = datetime.utcnow()

        usage = AITokenUsage(
            user_id=user.id,
            model_config_id=model_cfg.id,
            model_name=model_cfg.model,
            usage_type="block_analysis",
            prompt_tokens=result.usage["prompt_tokens"],
            completion_tokens=result.usage["completion_tokens"],
            total_tokens=result.usage["total_tokens"],
            estimated=result.usage_estimated,
            request_status="success",
            related_job_id=job.id,
            related_block_analysis_id=analysis.id,
        )
        session.add(usage)
        session.flush()
        analysis.token_usage_id = usage.id
    except Exception as exc:
        analysis.status = "failed"
        analysis.error_message = str(exc)[:500]
        job.status = "failed"
        job.failed_count = 1
        job.error_message = str(exc)[:500]
        job.finished_at = datetime.utcnow()
    session.flush()
    return analysis
```

- [ ] **Step 5: Run service tests**

Run:

```bash
cd backend
pytest tests/test_ai_block_analysis.py -q
```

Expected: all block analysis tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/ai_block_analysis.py backend/app/services/ai_block_analysis.py backend/tests/test_ai_block_analysis.py
git commit -m "feat(ai): add cached block analysis service"
```

---

## Task 5: Block Analysis And Admin APIs

**Files:**
- Create: `backend/app/api/ai.py`
- Modify: `backend/app/api/admin.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_admin_users_usage.py`
- Modify: `backend/tests/test_ai_block_analysis.py`

- [ ] **Step 1: Add failing API tests**

Append to `backend/tests/test_ai_block_analysis.py`:

```python
from app.services.auth_service import create_token


def test_block_analysis_requires_login(client):
    response = client.post("/api/ai/block-analyses", json={"page_route": "/topics/stocks", "block_id": 1})
    assert response.status_code == 401


def test_block_analysis_api_returns_cache_for_logged_in_user(client):
    session = next(client.app.dependency_overrides[get_session]())
    user, block = _seed_user_model_block(session)
    cached = AIBlockAnalysis(
        page_route="/topics/stocks",
        block_id=block.id,
        block_title=block.title,
        source_type=block.source_type,
        data_hash="manual-cache",
        status="generated",
        summary_points_json=["缓存"],
        expires_at=datetime.utcnow() + timedelta(minutes=30),
        generated_by_user_id=user.id,
    )
    session.add(cached)
    session.commit()
    token = create_token(user)

    response = client.get(
        "/api/ai/block-analyses",
        params={"page_route": "/topics/stocks", "block_id": block.id, "data_hash": "manual-cache"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["summary_points"] == ["缓存"]
```

Create `backend/tests/test_admin_users_usage.py`:

```python
from app.core.database import get_session
from app.models.entities import AITokenUsage, User
from app.services.auth_service import create_token


def _admin_token(session):
    admin = User(username="admin", email="", password_hash="hash", role="admin", status="active")
    session.add(admin)
    session.commit()
    return create_token(admin)


def test_admin_lists_users_and_can_disable_user(client):
    session = next(client.app.dependency_overrides[get_session]())
    token = _admin_token(session)
    user = User(username="alice", email="", password_hash="hash", role="user", status="active")
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
```

- [ ] **Step 2: Run API tests to verify failure**

Run:

```bash
cd backend
pytest tests/test_ai_block_analysis.py::test_block_analysis_requires_login tests/test_ai_block_analysis.py::test_block_analysis_api_returns_cache_for_logged_in_user tests/test_admin_users_usage.py -q
```

Expected: fail because `/api/ai/block-analyses`, `/api/admin/users`, and `/api/admin/ai/token-usages` do not exist.

- [ ] **Step 3: Add AI API router**

Create `backend/app/api/ai.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_session
from app.models.entities import AIBlockAnalysis, AITokenUsage, User
from app.schemas.ai_block_analysis import BlockAnalysisRead
from app.services.ai_block_analysis import analyze_block

router = APIRouter(prefix="/api/ai", tags=["ai"])


def _read_analysis(session: Session, analysis: AIBlockAnalysis) -> BlockAnalysisRead:
    usage = session.get(AITokenUsage, analysis.token_usage_id) if analysis.token_usage_id else None
    return BlockAnalysisRead(
        id=analysis.id,
        page_route=analysis.page_route,
        block_id=analysis.block_id,
        block_title=analysis.block_title,
        status=analysis.status,
        summary_points=analysis.summary_points_json,
        key_changes=analysis.key_changes_json,
        risk_points=analysis.risk_points_json,
        related_entities=analysis.related_entities_json,
        evidence_refs=analysis.evidence_refs_json,
        generated_by_model=analysis.generated_by_model,
        prompt_tokens=usage.prompt_tokens if usage else 0,
        completion_tokens=usage.completion_tokens if usage else 0,
        total_tokens=usage.total_tokens if usage else 0,
        token_estimated=usage.estimated if usage else False,
        generated_at=analysis.generated_at,
        expires_at=analysis.expires_at,
    )


@router.get("/block-analyses", response_model=BlockAnalysisRead)
def get_block_analysis(
    page_route: str = Query(...),
    block_id: int = Query(...),
    data_hash: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> BlockAnalysisRead:
    query = select(AIBlockAnalysis).where(
        AIBlockAnalysis.page_route == page_route,
        AIBlockAnalysis.block_id == block_id,
        AIBlockAnalysis.status == "generated",
    )
    if data_hash:
        query = query.where(AIBlockAnalysis.data_hash == data_hash)
    analysis = session.scalar(query.order_by(AIBlockAnalysis.generated_at.desc()).limit(1))
    if analysis is None:
        raise HTTPException(status_code=404, detail="No cached analysis")
    return _read_analysis(session, analysis)


@router.post("/block-analyses", response_model=BlockAnalysisRead)
def create_block_analysis(
    payload: dict,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> BlockAnalysisRead:
    analysis = analyze_block(
        session,
        user=user,
        page_route=str(payload.get("page_route", "")),
        block_id=int(payload.get("block_id", 0)),
    )
    session.commit()
    return _read_analysis(session, analysis)
```

Add to `backend/app/main.py`:

```python
from app.api import ai

app.include_router(ai.router)
```

- [ ] **Step 4: Add admin endpoints**

In `backend/app/api/admin.py`, import:

```python
from app.models.entities import AITokenUsage, AIBlockAnalysis, User
from app.schemas.auth import UserRead
from app.services.ai_block_analysis import analyze_block
```

Add endpoints before topic routes:

```python
@router.get("/users")
def list_users(session: Session = Depends(get_session)) -> list[dict]:
    users = session.scalars(select(User).order_by(User.created_at.desc())).all()
    return [
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "status": user.status,
            "last_login_at": user.last_login_at,
            "created_at": user.created_at,
        }
        for user in users
    ]


@router.patch("/users/{user_id}")
def update_user_status(user_id: int, payload: dict, session: Session = Depends(get_session)) -> dict:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    status = payload.get("status")
    if status not in {"active", "disabled"}:
        raise HTTPException(status_code=400, detail="Invalid status")
    user.status = status
    session.commit()
    return {"id": user.id, "status": user.status}


@router.get("/ai/token-usages")
def list_token_usages(page: int = 1, page_size: int = 20, session: Session = Depends(get_session)) -> dict:
    total = session.scalar(select(func.count()).select_from(AITokenUsage)) or 0
    usages = session.scalars(
        select(AITokenUsage).order_by(AITokenUsage.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": usage.id,
                "user_id": usage.user_id,
                "model_name": usage.model_name,
                "usage_type": usage.usage_type,
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
                "estimated": usage.estimated,
                "request_status": usage.request_status,
                "created_at": usage.created_at,
            }
            for usage in usages
        ],
    }
```

Add admin regenerate:

```python
@router.post("/ai/block-analyses/{analysis_id}/regenerate")
def regenerate_block_analysis(analysis_id: int, session: Session = Depends(get_session), admin: User = Depends(get_current_user)) -> dict:
    previous = session.get(AIBlockAnalysis, analysis_id)
    if previous is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    analysis = analyze_block(
        session,
        user=admin,
        page_route=previous.page_route,
        block_id=previous.block_id,
        force=True,
    )
    session.commit()
    return {"id": analysis.id, "status": analysis.status}
```

Ensure this function is protected by the router's admin dependency. If `get_current_user` is not imported, import it from `app.core.auth`.

- [ ] **Step 5: Run API tests**

Run:

```bash
cd backend
pytest tests/test_ai_block_analysis.py tests/test_admin_users_usage.py tests/test_auth_api.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/ai.py backend/app/api/admin.py backend/app/main.py backend/tests/test_ai_block_analysis.py backend/tests/test_admin_users_usage.py
git commit -m "feat(ai): expose block analysis APIs"
```

---

## Task 6: Frontend Auth Migration

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/hooks/use-auth.tsx`
- Modify: `frontend/src/pages/LoginPage.tsx`
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/__tests__/auth.test.tsx`

- [ ] **Step 1: Add failing frontend auth tests**

Create `frontend/src/__tests__/auth.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "@/api/client";
import { AuthProvider, useAuth } from "@/hooks/use-auth";
import { LoginPage } from "@/pages/LoginPage";

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={new QueryClient()}>
      <AuthProvider>
        <BrowserRouter>{children}</BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}

function AuthProbe() {
  const { user, isAuthenticated, isAdmin } = useAuth();
  return <div>{isAuthenticated ? `${user?.username}:${isAdmin}` : "anonymous"}</div>;
}

describe("auth", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("stores logged in user role", async () => {
    vi.spyOn(api, "post").mockResolvedValue({
      data: { token: "abc", user: { id: 1, username: "admin", email: "", role: "admin", status: "active" } },
    });

    render(
      <Wrapper>
        <LoginPage />
        <AuthProbe />
      </Wrapper>
    );

    await userEvent.type(screen.getByLabelText("密码"), "secret123");
    await userEvent.click(screen.getByRole("button", { name: "登录" }));

    await waitFor(() => expect(screen.getByText("admin:true")).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Run auth test to verify failure**

Run:

```bash
cd frontend
npm test -- src/__tests__/auth.test.tsx --runInBand
```

Expected: fail because `useAuth()` does not expose `user` or `isAdmin`.

- [ ] **Step 3: Add frontend auth types and API**

In `frontend/src/api/types.ts`, add:

```ts
export interface AuthUser {
  id: number;
  username: string;
  email: string | null;
  role: "admin" | "user";
  status: "active" | "disabled";
}

export interface AuthResponse {
  token: string;
  user: AuthUser;
}
```

In `frontend/src/api/client.ts`, import the types and add:

```ts
export function registerUser(data: { username: string; email: string; password: string }): Promise<AuthResponse> {
  return api.post<AuthResponse>("/api/auth/register", data).then((r) => r.data);
}

export function loginUser(data: { login: string; password: string }): Promise<AuthResponse> {
  return api.post<AuthResponse>("/api/auth/login", data).then((r) => r.data);
}

export function fetchMe(): Promise<AuthUser> {
  return api.get<AuthUser>("/api/auth/me").then((r) => r.data);
}
```

- [ ] **Step 4: Migrate auth hook**

Replace `frontend/src/hooks/use-auth.tsx` with:

```tsx
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import api, { fetchMe, loginUser, registerUser } from "@/api/client";
import type { AuthUser } from "@/api/types";

interface AuthContextType {
  token: string | null;
  user: AuthUser | null;
  login: (login: string, password: string) => Promise<void>;
  register: (username: string, email: string, password: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
  isAdmin: boolean;
}

const AuthContext = createContext<AuthContextType>({
  token: null,
  user: null,
  login: async () => {},
  register: async () => {},
  logout: () => {},
  isAuthenticated: false,
  isAdmin: false,
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(localStorage.getItem("auth_token") ?? localStorage.getItem("admin_token"));
  const [user, setUser] = useState<AuthUser | null>(() => {
    const raw = localStorage.getItem("auth_user");
    return raw ? JSON.parse(raw) : null;
  });

  useEffect(() => {
    if (token) {
      api.defaults.headers.common.Authorization = `Bearer ${token}`;
      fetchMe().then(setUser).catch(() => logout());
    } else {
      delete api.defaults.headers.common.Authorization;
    }
  }, [token]);

  const persist = (nextToken: string, nextUser: AuthUser) => {
    localStorage.setItem("auth_token", nextToken);
    localStorage.removeItem("admin_token");
    localStorage.setItem("auth_user", JSON.stringify(nextUser));
    api.defaults.headers.common.Authorization = `Bearer ${nextToken}`;
    setToken(nextToken);
    setUser(nextUser);
  };

  const login = async (loginValue: string, password: string) => {
    const res = await loginUser({ login: loginValue, password });
    persist(res.token, res.user);
  };

  const register = async (username: string, email: string, password: string) => {
    const res = await registerUser({ username, email, password });
    persist(res.token, res.user);
  };

  const logout = () => {
    localStorage.removeItem("auth_token");
    localStorage.removeItem("admin_token");
    localStorage.removeItem("auth_user");
    delete api.defaults.headers.common.Authorization;
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ token, user, login, register, logout, isAuthenticated: !!token && !!user, isAdmin: user?.role === "admin" }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
```

- [ ] **Step 5: Update protected route**

In `frontend/src/App.tsx`, change `ProtectedRoute`:

```tsx
function ProtectedRoute() {
  const { isAuthenticated, isAdmin } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (!isAdmin) return <Navigate to="/" replace />;
  return <AdminLayout />;
}
```

- [ ] **Step 6: Update login page**

Modify `frontend/src/pages/LoginPage.tsx` so it has a login/register toggle. The login form calls `login(loginValue, password)`, and the register form calls `register(username, email, password)`. The primary fields must have visible labels:

```tsx
<Label htmlFor="login-password">密码</Label>
<Input id="login-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
```

After success, navigate to `location.state?.from ?? "/"`.

- [ ] **Step 7: Run frontend auth tests**

Run:

```bash
cd frontend
npm test -- src/__tests__/auth.test.tsx
```

Expected: pass.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/api/types.ts frontend/src/api/client.ts frontend/src/hooks/use-auth.tsx frontend/src/pages/LoginPage.tsx frontend/src/App.tsx frontend/src/__tests__/auth.test.tsx
git commit -m "feat(auth): support public user login"
```

---

## Task 7: Frontend Block AI Drawer

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/components/layout/SectionHeading.tsx`
- Modify: `frontend/src/components/layout/GridRenderer.tsx`
- Create: `frontend/src/components/layout/BlockAIAnalysisDrawer.tsx`
- Test: `frontend/src/__tests__/block-ai-analysis.test.tsx`

- [ ] **Step 1: Add failing drawer tests**

Create `frontend/src/__tests__/block-ai-analysis.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { AuthProvider } from "@/hooks/use-auth";
import { GridRenderer } from "@/components/layout/GridRenderer";

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={new QueryClient()}>
      <AuthProvider>
        <BrowserRouter>{children}</BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}

describe("block ai analysis", () => {
  it("prompts anonymous users to log in", async () => {
    render(
      <Wrapper>
        <GridRenderer
          isLoading={false}
          blocks={[{ id: 1, title: "AI资讯", source_type: "aihot_news", col_span: 1, row_span: 1, data: [{ id: 1, title: "模型发布", summary: "更新" }] }]}
        />
      </Wrapper>
    );

    await userEvent.click(screen.getByRole("button", { name: /AI 分析/ }));
    expect(screen.getByText("登录后可使用 AI 分析")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run drawer test to verify failure**

Run:

```bash
cd frontend
npm test -- src/__tests__/block-ai-analysis.test.tsx
```

Expected: fail because there is no `AI 分析` button.

- [ ] **Step 3: Add analysis types and API calls**

In `frontend/src/api/types.ts`, add:

```ts
export interface BlockAIAnalysis {
  id: number;
  page_route: string;
  block_id: number;
  block_title: string;
  status: "processing" | "generated" | "failed";
  summary_points: string[];
  key_changes: string[];
  risk_points: string[];
  related_entities: string[];
  evidence_refs: { title: string; source?: string; published_at?: string | null; url?: string | null }[];
  generated_by_model: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  token_estimated: boolean;
  generated_at: string | null;
  expires_at: string | null;
}
```

In `frontend/src/api/client.ts`, add:

```ts
export function generateBlockAIAnalysis(data: { page_route: string; block_id: number }): Promise<BlockAIAnalysis> {
  return api.post<BlockAIAnalysis>("/api/ai/block-analyses", data).then((r) => r.data);
}
```

- [ ] **Step 4: Add action slot to section heading**

Modify `frontend/src/components/layout/SectionHeading.tsx`:

```tsx
export function SectionHeading({
  icon: Icon,
  title,
  meta,
  action,
  className,
}: {
  icon: LucideIcon;
  title: string;
  meta?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex min-w-0 items-center justify-between gap-3", className)}>
      <h2 className="flex min-w-0 items-center gap-2 text-sm font-semibold text-foreground/85">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-primary/20 bg-primary/10 text-primary">
          <Icon data-testid="section-heading-icon" className="h-3.5 w-3.5" aria-hidden="true" />
        </span>
        <span className="truncate">{title}</span>
      </h2>
      <div className="flex shrink-0 items-center gap-2">
        {meta ? <span className="text-[11px] text-muted-foreground">{meta}</span> : null}
        {action}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Add drawer component**

Create `frontend/src/components/layout/BlockAIAnalysisDrawer.tsx`:

```tsx
import { AnimatePresence, motion } from "framer-motion";
import { BrainCircuit, ChevronDown, Loader2, X } from "lucide-react";
import { useState } from "react";
import type { BlockAIAnalysis } from "@/api/types";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function BlockAIAnalysisDrawer({
  open,
  title,
  analysis,
  isLoading,
  error,
  requiresLogin,
  onClose,
}: {
  open: boolean;
  title: string;
  analysis: BlockAIAnalysis | null;
  isLoading: boolean;
  error: string | null;
  requiresLogin: boolean;
  onClose: () => void;
}) {
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  return (
    <AnimatePresence>
      {open ? (
        <motion.aside
          initial={{ opacity: 0, x: 24 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: 24 }}
          transition={{ duration: 0.2 }}
          className="fixed inset-x-0 bottom-0 z-50 max-h-[82dvh] rounded-t-2xl border bg-background shadow-2xl md:inset-x-auto md:right-4 md:top-4 md:h-[calc(100dvh-2rem)] md:w-[420px] md:max-h-none md:rounded-xl"
          aria-label="AI 分析"
        >
          <div className="flex h-full flex-col">
            <header className="flex items-center justify-between border-b px-5 py-4">
              <div className="min-w-0">
                <div className="flex items-center gap-2 text-sm font-semibold">
                  <BrainCircuit className="h-4 w-4 text-primary" aria-hidden="true" />
                  <span className="truncate">{title}</span>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">区块级 AI 分析</p>
              </div>
              <Button variant="ghost" size="icon" aria-label="关闭 AI 分析" onClick={onClose}>
                <X className="h-4 w-4" />
              </Button>
            </header>

            <div className="flex-1 space-y-5 overflow-y-auto px-5 py-4">
              {requiresLogin ? <p className="rounded-lg border bg-muted/40 p-4 text-sm">登录后可使用 AI 分析</p> : null}
              {isLoading ? <div className="space-y-3"><div className="h-4 w-2/3 animate-pulse rounded bg-muted" /><div className="h-20 animate-pulse rounded bg-muted" /></div> : null}
              {error ? <p className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">{error}</p> : null}
              {analysis ? (
                <>
                  <section>
                    <h3 className="mb-2 text-xs font-medium text-muted-foreground">核心总结</h3>
                    <ul className="space-y-2">
                      {analysis.summary_points.map((item) => <li key={item} className="rounded-lg bg-muted/50 px-3 py-2 text-sm leading-6">{item}</li>)}
                    </ul>
                  </section>
                  {analysis.key_changes.length > 0 ? <InsightList title="关键变化" items={analysis.key_changes} /> : null}
                  {analysis.risk_points.length > 0 ? <InsightList title="风险/不确定性" items={analysis.risk_points} /> : null}
                  {analysis.related_entities.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {analysis.related_entities.map((item) => <span key={item} className="rounded-md border px-2 py-1 text-xs">{item}</span>)}
                    </div>
                  ) : null}
                  <button className="flex w-full items-center justify-between rounded-lg border px-3 py-2 text-sm" onClick={() => setEvidenceOpen((value) => !value)}>
                    <span>分析依据 {analysis.evidence_refs.length} 条</span>
                    <ChevronDown className={cn("h-4 w-4 transition-transform", evidenceOpen && "rotate-180")} />
                  </button>
                  {evidenceOpen ? (
                    <div className="space-y-2">
                      {analysis.evidence_refs.map((item, index) => <p key={`${item.title}-${index}`} className="text-xs leading-5 text-muted-foreground">{item.title}</p>)}
                    </div>
                  ) : null}
                </>
              ) : null}
            </div>
          </div>
        </motion.aside>
      ) : null}
    </AnimatePresence>
  );
}

function InsightList({ title, items }: { title: string; items: string[] }) {
  return (
    <section>
      <h3 className="mb-2 text-xs font-medium text-muted-foreground">{title}</h3>
      <ul className="space-y-2">
        {items.map((item) => <li key={item} className="text-sm leading-6">{item}</li>)}
      </ul>
    </section>
  );
}
```

- [ ] **Step 6: Wire drawer in GridRenderer**

In `frontend/src/components/layout/GridRenderer.tsx`, import:

```tsx
import { BrainCircuit } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import { generateBlockAIAnalysis } from "@/api/client";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { BlockAIAnalysisDrawer } from "./BlockAIAnalysisDrawer";
```

Inside `GridRenderer`, add state before returns:

```tsx
  const { isAuthenticated } = useAuth();
  const [selectedBlock, setSelectedBlock] = useState<any | null>(null);
  const [requiresLogin, setRequiresLogin] = useState(false);
  const analysisMutation = useMutation({
    mutationFn: generateBlockAIAnalysis,
  });
```

Add action to `SectionHeading`:

```tsx
<SectionHeading
  icon={sectionIcon(st)}
  title={block.title}
  action={
    <Button
      variant="ghost"
      size="sm"
      className="h-7 gap-1.5 px-2 text-xs"
      onClick={() => {
        setSelectedBlock(block);
        if (!isAuthenticated) {
          setRequiresLogin(true);
          return;
        }
        setRequiresLogin(false);
        analysisMutation.mutate({ page_route: block.page_route, block_id: block.id });
      }}
    >
      <BrainCircuit className="h-3.5 w-3.5" aria-hidden="true" />
      AI 分析
    </Button>
  }
/>
```

Render drawer next to the grid:

```tsx
<BlockAIAnalysisDrawer
  open={Boolean(selectedBlock)}
  title={selectedBlock?.title ?? ""}
  analysis={analysisMutation.data ?? null}
  isLoading={analysisMutation.isPending}
  error={analysisMutation.error ? analysisMutation.error.message : null}
  requiresLogin={requiresLogin}
  onClose={() => {
    setSelectedBlock(null);
    setRequiresLogin(false);
    analysisMutation.reset();
  }}
/>
```

If the component currently returns the grid directly, wrap the grid and drawer in a fragment.

- [ ] **Step 7: Run drawer tests**

Run:

```bash
cd frontend
npm test -- src/__tests__/block-ai-analysis.test.tsx
```

Expected: pass.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/api/types.ts frontend/src/api/client.ts frontend/src/components/layout/SectionHeading.tsx frontend/src/components/layout/GridRenderer.tsx frontend/src/components/layout/BlockAIAnalysisDrawer.tsx frontend/src/__tests__/block-ai-analysis.test.tsx
git commit -m "feat(ai): add block analysis drawer"
```

---

## Task 8: Admin Users And Token Usage Pages

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/client.ts`
- Create: `frontend/src/pages/AdminUsersPage.tsx`
- Create: `frontend/src/pages/AdminAIUsagePage.tsx`
- Modify: `frontend/src/components/admin/AdminSidebar.tsx`
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/__tests__/admin-users-usage.test.tsx`

- [ ] **Step 1: Add failing admin page tests**

Create `frontend/src/__tests__/admin-users-usage.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import api from "@/api/client";
import { AdminUsersPage } from "@/pages/AdminUsersPage";
import { AdminAIUsagePage } from "@/pages/AdminAIUsagePage";

function Wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={new QueryClient()}><BrowserRouter>{children}</BrowserRouter></QueryClientProvider>;
}

describe("admin users and usage", () => {
  it("renders users", async () => {
    vi.spyOn(api, "get").mockResolvedValue({ data: [{ id: 1, username: "alice", role: "user", status: "active", created_at: "2026-06-05" }] });
    render(<AdminUsersPage />, { wrapper: Wrapper });
    expect(await screen.findByText("alice")).toBeInTheDocument();
  });

  it("renders token usage", async () => {
    vi.spyOn(api, "get").mockResolvedValue({ data: { total: 1, page: 1, page_size: 20, items: [{ id: 1, user_id: 1, model_name: "free", usage_type: "block_analysis", total_tokens: 88, estimated: false, request_status: "success", created_at: "2026-06-05" }] } });
    render(<AdminAIUsagePage />, { wrapper: Wrapper });
    expect(await screen.findByText("88")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run admin page tests to verify failure**

Run:

```bash
cd frontend
npm test -- src/__tests__/admin-users-usage.test.tsx
```

Expected: fail because pages do not exist.

- [ ] **Step 3: Add admin types and API**

In `frontend/src/api/types.ts`, add:

```ts
export interface AdminUser {
  id: number;
  username: string;
  email: string | null;
  role: "admin" | "user";
  status: "active" | "disabled";
  last_login_at: string | null;
  created_at: string;
}

export interface AITokenUsage {
  id: number;
  user_id: number | null;
  model_name: string;
  usage_type: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  estimated: boolean;
  request_status: string;
  created_at: string;
}

export interface AITokenUsageListResponse {
  total: number;
  page: number;
  page_size: number;
  items: AITokenUsage[];
}
```

In `frontend/src/api/client.ts`, add:

```ts
export function fetchAdminUsers(): Promise<AdminUser[]> {
  return api.get<AdminUser[]>("/api/admin/users").then((r) => r.data);
}

export function updateAdminUserStatus(id: number, status: "active" | "disabled"): Promise<{ id: number; status: string }> {
  return api.patch(`/api/admin/users/${id}`, { status }).then((r) => r.data);
}

export function fetchAITokenUsages(page = 1, pageSize = 20): Promise<AITokenUsageListResponse> {
  return api.get<AITokenUsageListResponse>("/api/admin/ai/token-usages", { params: { page, page_size: pageSize } }).then((r) => r.data);
}
```

- [ ] **Step 4: Add admin user page**

Create `frontend/src/pages/AdminUsersPage.tsx`:

```tsx
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchAdminUsers, updateAdminUserStatus } from "@/api/client";
import { AdminPageHeader } from "@/components/admin/AdminPageHeader";
import { Button } from "@/components/ui/button";

export function AdminUsersPage() {
  const queryClient = useQueryClient();
  const { data: users = [], isLoading } = useQuery({ queryKey: ["admin-users"], queryFn: fetchAdminUsers });
  const mutation = useMutation({
    mutationFn: ({ id, status }: { id: number; status: "active" | "disabled" }) => updateAdminUserStatus(id, status),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-users"] }),
  });

  return (
    <div className="space-y-5">
      <AdminPageHeader eyebrow="Users" title="用户管理" description="查看注册用户并启用或禁用 AI 使用权限。" />
      <div className="overflow-hidden rounded-lg border bg-card">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-muted-foreground">
            <tr><th className="px-4 py-3 text-left">用户</th><th className="px-4 py-3 text-left">角色</th><th className="px-4 py-3 text-left">状态</th><th className="px-4 py-3 text-right">操作</th></tr>
          </thead>
          <tbody>
            {isLoading ? <tr><td className="px-4 py-4" colSpan={4}>加载中</td></tr> : users.map((user) => (
              <tr key={user.id} className="border-t">
                <td className="px-4 py-3">{user.username}</td>
                <td className="px-4 py-3">{user.role}</td>
                <td className="px-4 py-3">{user.status}</td>
                <td className="px-4 py-3 text-right">
                  <Button size="sm" variant="outline" onClick={() => mutation.mutate({ id: user.id, status: user.status === "active" ? "disabled" : "active" })}>
                    {user.status === "active" ? "禁用" : "启用"}
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Add token usage page**

Create `frontend/src/pages/AdminAIUsagePage.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query";
import { fetchAITokenUsages } from "@/api/client";
import { AdminPageHeader } from "@/components/admin/AdminPageHeader";

export function AdminAIUsagePage() {
  const { data, isLoading } = useQuery({ queryKey: ["ai-token-usages"], queryFn: () => fetchAITokenUsages(1, 20) });
  return (
    <div className="space-y-5">
      <AdminPageHeader eyebrow="AI Usage" title="AI 用量" description="查看用户、模型和场景的 token 使用记录。" />
      <div className="overflow-hidden rounded-lg border bg-card">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-muted-foreground">
            <tr><th className="px-4 py-3 text-left">用户</th><th className="px-4 py-3 text-left">模型</th><th className="px-4 py-3 text-left">场景</th><th className="px-4 py-3 text-right">Token</th></tr>
          </thead>
          <tbody>
            {isLoading ? <tr><td className="px-4 py-4" colSpan={4}>加载中</td></tr> : data?.items.map((item) => (
              <tr key={item.id} className="border-t">
                <td className="px-4 py-3">{item.user_id ?? "-"}</td>
                <td className="px-4 py-3">{item.model_name}</td>
                <td className="px-4 py-3">{item.usage_type}</td>
                <td className="px-4 py-3 text-right tabular-nums">{item.total_tokens}{item.estimated ? " 估算" : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Add routes and sidebar**

In `frontend/src/App.tsx`, import pages and add admin routes:

```tsx
import { AdminUsersPage } from "./pages/AdminUsersPage";
import { AdminAIUsagePage } from "./pages/AdminAIUsagePage";
```

```tsx
<Route path="/admin/users" element={<AdminUsersPage />} />
<Route path="/admin/ai-usage" element={<AdminAIUsagePage />} />
```

In `frontend/src/components/admin/AdminSidebar.tsx`, add nav items:

```tsx
{ href: "/admin/users", label: "用户", icon: Users },
{ href: "/admin/ai-usage", label: "AI 用量", icon: Gauge },
```

Import `Users` and `Gauge` from `lucide-react`.

- [ ] **Step 7: Run admin frontend tests**

Run:

```bash
cd frontend
npm test -- src/__tests__/admin-users-usage.test.tsx
```

Expected: pass.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/api/types.ts frontend/src/api/client.ts frontend/src/pages/AdminUsersPage.tsx frontend/src/pages/AdminAIUsagePage.tsx frontend/src/components/admin/AdminSidebar.tsx frontend/src/App.tsx frontend/src/__tests__/admin-users-usage.test.tsx
git commit -m "feat(admin): show users and ai token usage"
```

---

## Task 9: Full Verification And Polish

**Files:**
- Modify only files already touched in Tasks 1-8 when verification reveals a concrete defect.

- [ ] **Step 1: Run backend targeted tests**

Run:

```bash
cd backend
pytest tests/test_auth_api.py tests/test_ai_block_analysis.py tests/test_admin_users_usage.py tests/test_ai_enrichment.py tests/test_jobs_ai_integration.py tests/test_ai_admin_api.py -q
```

Expected: pass.

- [ ] **Step 2: Run backend suite excluding known external network test if needed**

Run:

```bash
cd backend
pytest -q -k "not test_gainers"
```

Expected: pass. If `test_gainers` is run separately, it may fail due external Eastmoney DNS and should be reported as an external-network residual risk.

- [ ] **Step 3: Run frontend tests**

Run:

```bash
cd frontend
npm test -- --run
```

Expected: all frontend tests pass.

- [ ] **Step 4: Run frontend build**

Run:

```bash
cd frontend
npm run build
```

Expected: Vite build succeeds. Existing large chunk warning is acceptable if unchanged.

- [ ] **Step 5: Run migration check**

Run:

```bash
cd backend
python -m alembic upgrade head
```

Expected: migrations apply to head without MySQL TEXT or JSON default errors.

- [ ] **Step 6: Manual browser verification**

Start backend and frontend using the existing local workflow:

```bash
cd backend
/Users/lws/opt/anaconda3/envs/daily_highlights/bin/uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5175
```

Verify:

- `/topics/stocks`, `/topics/ai`, `/topics/football` still render existing blocks.
- Anonymous click on `AI 分析` opens login prompt.
- Registered user can generate block analysis.
- A second click on unchanged data returns cached analysis.
- Admin can see `/admin/users` and `/admin/ai-usage`.
- Mobile viewport shows bottom Sheet instead of a cramped side panel.

- [ ] **Step 7: Run diff check**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors. Status should only show intentional final changes if execution stopped before commit.

- [ ] **Step 8: Final commit if polish changed files**

If Task 9 required code changes, commit them:

```bash
git status --short
git add backend/app/models/entities.py backend/app/core/auth.py backend/app/api/auth.py backend/app/api/ai.py backend/app/api/admin.py backend/app/services/auth_service.py backend/app/services/ai_block_analysis.py backend/app/services/ai_client.py backend/app/services/token_usage.py frontend/src/hooks/use-auth.tsx frontend/src/components/layout/GridRenderer.tsx frontend/src/components/layout/BlockAIAnalysisDrawer.tsx frontend/src/pages/LoginPage.tsx frontend/src/pages/AdminUsersPage.tsx frontend/src/pages/AdminAIUsagePage.tsx
git commit -m "fix(ai): polish block analysis auth flow"
```

If no files changed in Task 9, do not create an empty commit.
