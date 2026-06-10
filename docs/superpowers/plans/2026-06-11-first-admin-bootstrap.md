# First Admin Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the public default administrator password with a one-time browser bootstrap flow, explicit database initialization, and closed public registration.

**Architecture:** A focused backend bootstrap service owns setup-state detection, legacy account handling, and the transactional creation of the first administrator. FastAPI exposes setup status and bootstrap endpoints; Alembic and a small initialization script own schema/default-data setup; React selects either the bootstrap form or login form from server state.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Alembic, Pydantic, pytest, React 18, TypeScript, Axios, Vitest, Testing Library.

---

## File Map

- Create `backend/app/services/admin_bootstrap.py`: bootstrap state, legacy default account detection, and transactional administrator creation.
- Create `backend/scripts/init_db.py`: run Alembic and reconcile legacy bootstrap metadata without accepting passwords.
- Create `backend/migrations/versions/20260611_0011_admin_bootstrap.py`: seed the default stocks topic and remove obsolete plaintext admin-password setting.
- Modify `backend/app/api/auth.py`: add setup/bootstrap routes and remove public registration.
- Modify `backend/app/schemas/auth.py`: add setup response schema.
- Modify `backend/app/core/auth.py`: retain request authentication only; remove default-password code.
- Modify `backend/app/api/admin.py`: remove legacy admin login router.
- Modify `backend/app/main.py`: remove startup database writes.
- Modify `backend/tests/test_auth_api.py`: cover bootstrap, login, closed registration, and legacy account recovery.
- Create `backend/tests/test_init_db.py`: cover post-migration reconciliation helpers.
- Modify `frontend/src/api/client.ts`: expose setup and bootstrap calls; remove public register call.
- Modify `frontend/src/api/types.ts`: add setup response type.
- Modify `frontend/src/hooks/use-auth.tsx`: expose `bootstrapAdmin` and remove public register API.
- Modify `frontend/src/pages/LoginPage.tsx`: server-driven first-admin form, failure/retry state, and normal login.
- Modify `frontend/src/__tests__/auth.test.tsx`: cover bootstrap and login modes without real network calls.
- Modify `README.md` and `CLAUDE.md`: document database initialization and valid Fernet test key.

### Task 1: Backend Bootstrap Behavior

**Files:**
- Create: `backend/app/services/admin_bootstrap.py`
- Modify: `backend/app/schemas/auth.py`
- Modify: `backend/app/api/auth.py`
- Test: `backend/tests/test_auth_api.py`

- [ ] **Step 1: Replace registration tests with failing bootstrap tests**

Add tests that assert:

```python
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


def test_second_bootstrap_is_rejected(client):
    payload = {"username": "owner", "email": "", "password": "secret123"}
    assert client.post("/api/auth/bootstrap-admin", json=payload).status_code == 200
    response = client.post(
        "/api/auth/bootstrap-admin",
        json={"username": "other", "email": "", "password": "secret456"},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Administrator already initialized"


def test_public_registration_route_is_removed(client):
    response = client.post(
        "/api/auth/register",
        json={"username": "alice", "email": "", "password": "secret123"},
    )
    assert response.status_code == 404
```

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```bash
cd backend
APP_SECRET_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= \
  python -m pytest tests/test_auth_api.py -q
```

Expected: failures for missing `/setup-status` and `/bootstrap-admin`, and the old registration route still returning `200`.

- [ ] **Step 3: Implement setup status and transactional bootstrap**

Implement constants and functions in `admin_bootstrap.py`:

```python
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


def bootstrap_admin(session: Session, username: str, email: str, password: str) -> User:
    if not setup_required(session):
        raise HTTPException(status_code=409, detail="Administrator already initialized")
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
        select(User).where(User.username == LEGACY_USERNAME, User.role == "admin")
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
```

`setup_required()` returns false when the completion marker exists or a non-legacy active admin exists. `bootstrap_admin()` inserts the unique completion marker, re-checks state, updates or disables the legacy account, creates the administrator when needed, deletes the obsolete password setting, and commits once. Convert marker uniqueness conflicts into HTTP `409`.

Add:

```python
class SetupStatusResponse(BaseModel):
    setup_required: bool
```

Expose:

```python
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
```

Remove `/api/auth/register`.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the command from Step 2. Expected: all tests in `test_auth_api.py` pass.

- [ ] **Step 5: Commit backend bootstrap API**

```bash
git add backend/app/services/admin_bootstrap.py backend/app/schemas/auth.py \
  backend/app/api/auth.py backend/tests/test_auth_api.py
git commit -m "feat(auth): add first admin bootstrap API"
```

### Task 2: Legacy Default Account and Old Login Removal

**Files:**
- Modify: `backend/app/core/auth.py`
- Modify: `backend/app/api/admin.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_auth_api.py`

- [ ] **Step 1: Add failing legacy and startup tests**

Add tests proving:

```python
def test_legacy_default_admin_does_not_close_setup(client):
    session = next(client.app.dependency_overrides[get_session]())
    legacy = create_user(session, "admin", "", "admin123", role="admin")
    session.commit()
    assert client.get("/api/auth/setup-status").json() == {"setup_required": True}


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
    replaced = session.get(User, legacy_id)
    assert replaced.email == "owner@example.com"
    assert verify_password("new-secret", replaced.password_hash)
    assert not verify_password("admin123", replaced.password_hash)


def test_changed_admin_password_is_treated_as_initialized(client):
    session = next(client.app.dependency_overrides[get_session]())
    create_user(session, "admin", "", "changed-secret", role="admin")
    session.commit()
    assert client.get("/api/auth/setup-status").json() == {"setup_required": False}


def test_legacy_admin_login_route_is_removed(client):
    response = client.post("/api/admin/login", json={"password": "admin123"})
    assert response.status_code == 404
```

The in-place replacement test records the legacy user ID, bootstraps username `admin`, then verifies the same ID now authenticates with the new password and `admin123` fails.

Add a direct lifespan test or source-level assertion proving app startup no longer calls `Base.metadata.create_all()` or any seed function.

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```bash
cd backend
APP_SECRET_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= \
  python -m pytest tests/test_auth_api.py -q
```

Expected: legacy login and startup-write assertions fail.

- [ ] **Step 3: Remove default-password authentication and startup writes**

Reduce `core/auth.py` to bearer-token helpers:

```python
security = HTTPBearer(auto_error=False)

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
```

Delete `DEFAULT_PASSWORD`, `create_admin_token()`, and `seed_default_password()`.

Delete `auth_router`, its local `LoginRequest`, and `/api/admin/login` from `api/admin.py`. Stop including `admin.auth_router` in `main.py`. Remove `_seed_defaults()`, `Base`, `SessionLocal`, `engine`, `Topic`, and startup exception swallowing from `main.py`.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the command from Step 2. Expected: all auth tests pass.

- [ ] **Step 5: Commit legacy removal**

```bash
git add backend/app/core/auth.py backend/app/api/admin.py backend/app/main.py \
  backend/tests/test_auth_api.py
git commit -m "fix(auth): remove automatic default administrator"
```

### Task 3: Database Migration and Initialization Script

**Files:**
- Create: `backend/migrations/versions/20260611_0011_admin_bootstrap.py`
- Create: `backend/scripts/init_db.py`
- Create: `backend/tests/test_init_db.py`

- [ ] **Step 1: Add failing initialization helper tests**

Test a helper `reconcile_bootstrap_state(session)`:

```python
def test_reconcile_marks_existing_real_admin_complete(db_session):
    create_user(db_session, "owner", "", "secret123", role="admin")
    reconcile_bootstrap_state(db_session)
    assert db_session.get(AppSetting, BOOTSTRAP_COMPLETED_KEY) is not None


def test_reconcile_leaves_only_legacy_admin_open(db_session):
    create_user(db_session, "admin", "", "admin123", role="admin")
    reconcile_bootstrap_state(db_session)
    assert db_session.get(AppSetting, BOOTSTRAP_COMPLETED_KEY) is None


def test_reconcile_removes_plaintext_password_setting(db_session):
    set_plain_setting(db_session, LEGACY_PASSWORD_KEY, "admin123")
    reconcile_bootstrap_state(db_session)
    assert db_session.get(AppSetting, LEGACY_PASSWORD_KEY) is None
```

Also test that the script entrypoint calls Alembic `upgrade(config, "head")` before reconciliation by injecting callable dependencies into `main()`.

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
cd backend
APP_SECRET_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= \
  python -m pytest tests/test_init_db.py -q
```

Expected: import failure because `scripts/init_db.py` does not exist.

- [ ] **Step 3: Implement migration and script**

Migration `0011`, down revision `0010`, performs:

```python
topics = sa.table(
    "topics",
    sa.column("name", sa.String()),
    sa.column("slug", sa.String()),
    sa.column("sort_order", sa.Integer()),
    sa.column("enabled", sa.Boolean()),
)
op.execute(
    sa.insert(topics).from_select(
        ["name", "slug", "sort_order", "enabled"],
        sa.select(
            sa.literal("股票"),
            sa.literal("stocks"),
            sa.literal(1),
            sa.literal(True),
        ).where(
            ~sa.exists(sa.select(sa.literal(1)).where(topics.c.slug == "stocks"))
        ),
    )
)
op.execute(
    sa.text("DELETE FROM app_settings WHERE `key` = :key").bindparams(key="admin.password")
)
```

Use dialect-compatible SQLAlchemy expressions, not MySQL-only raw insert syntax.

`scripts/init_db.py` uses `alembic.command.upgrade`, then opens `SessionLocal`, calls `reconcile_bootstrap_state()`, commits, and prints the browser bootstrap next step. `main()` returns non-zero by propagating migration or database errors.

- [ ] **Step 4: Run initialization tests and migration syntax checks**

Run:

```bash
cd backend
APP_SECRET_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= \
  python -m pytest tests/test_init_db.py -q
python -m compileall -q scripts migrations/versions/20260611_0011_admin_bootstrap.py
```

Expected: tests pass and compile command exits `0`.

- [ ] **Step 5: Commit initialization flow**

```bash
git add backend/migrations/versions/20260611_0011_admin_bootstrap.py \
  backend/scripts/init_db.py backend/tests/test_init_db.py
git commit -m "feat(db): add explicit database initialization"
```

### Task 4: Frontend Setup State and Authentication API

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/hooks/use-auth.tsx`
- Modify: `frontend/src/__tests__/auth.test.tsx`

- [ ] **Step 1: Add failing AuthProvider bootstrap test**

Mock Axios methods explicitly:

```typescript
vi.spyOn(api, "get").mockResolvedValueOnce({ data: { setup_required: true } });
vi.spyOn(api, "post").mockResolvedValueOnce({
  data: {
    token: "abc",
    user: { id: 1, username: "owner", email: "", role: "admin", status: "active" },
  },
});
```

Render the provider and assert calling `bootstrapAdmin()` stores `auth_token`, `auth_user`, and exposes `isAdmin=true`.

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
cd frontend
npx vitest run src/__tests__/auth.test.tsx
```

Expected: `bootstrapAdmin` is missing.

- [ ] **Step 3: Implement frontend API and provider method**

Add:

```typescript
export interface SetupStatus {
  setup_required: boolean;
}

export function fetchSetupStatus(): Promise<SetupStatus> {
  return api.get<SetupStatus>("/api/auth/setup-status").then((response) => response.data);
}

export function bootstrapAdmin(data: {
  username: string;
  email: string;
  password: string;
}): Promise<AuthResponse> {
  return api.post<AuthResponse>("/api/auth/bootstrap-admin", data).then((response) => response.data);
}
```

Remove `registerUser`. Replace `register` in `AuthContextType` with:

```typescript
bootstrapAdmin: (username: string, email: string, password: string) => Promise<void>;
```

Keep one shared `persist()` path for login and bootstrap. Continue removing legacy `admin_token` from storage during migration, but never create it.

- [ ] **Step 4: Run test and verify GREEN**

Run the command from Step 2. Expected: provider tests pass with no real HTTP request.

- [ ] **Step 5: Commit frontend auth API**

```bash
git add frontend/src/api/types.ts frontend/src/api/client.ts \
  frontend/src/hooks/use-auth.tsx frontend/src/__tests__/auth.test.tsx
git commit -m "feat(frontend): add administrator bootstrap client"
```

### Task 5: First-Run Login Page

**Files:**
- Modify: `frontend/src/pages/LoginPage.tsx`
- Modify: `frontend/src/__tests__/auth.test.tsx`

- [ ] **Step 1: Add failing page-mode tests**

Cover:

```typescript
it("shows administrator creation when setup is required", async () => {
  vi.spyOn(api, "get").mockResolvedValue({ data: { setup_required: true } });
  renderLoginPage();
  expect(await screen.findByRole("heading", { name: "创建管理员" })).toBeInTheDocument();
  expect(screen.getByLabelText("确认密码")).toBeInTheDocument();
});

it("shows login without a public registration link after setup", async () => {
  vi.spyOn(api, "get").mockResolvedValue({ data: { setup_required: false } });
  renderLoginPage();
  expect(await screen.findByRole("button", { name: "登录" })).toBeInTheDocument();
  expect(screen.queryByText("没有账户？")).not.toBeInTheDocument();
});

it("does not expose bootstrap form when setup status fails", async () => {
  vi.spyOn(api, "get").mockRejectedValue(new Error("offline"));
  renderLoginPage();
  expect(await screen.findByRole("button", { name: "重试" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "创建管理员" })).not.toBeInTheDocument();
});

it("switches to login after bootstrap conflict", async () => {
  vi.spyOn(api, "get")
    .mockResolvedValueOnce({ data: { setup_required: true } })
    .mockResolvedValueOnce({ data: { setup_required: false } });
  vi.spyOn(api, "post").mockRejectedValue(
    Object.assign(new Error("Administrator already initialized"), { status: 409 }),
  );
  renderLoginPage();
  await submitBootstrapForm();
  expect(await screen.findByRole("button", { name: "登录" })).toBeInTheDocument();
});
```

Assertions include `创建管理员`, `确认密码`, explicit `用户名或邮箱`, absence of `没有账户？`, and a retry button for status failures.

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
cd frontend
npx vitest run src/__tests__/auth.test.tsx
```

Expected: current manual login/register toggle violates all new mode assertions.

- [ ] **Step 3: Implement server-driven page state**

Use a state machine:

```typescript
type SetupState = "loading" | "bootstrap" | "login" | "error";
```

On mount, call `fetchSetupStatus()`. Render loading, retryable error, bootstrap, or login form. Bootstrap includes username, optional email, password, and confirmation. Login requires explicit username/email and does not fall back to `"admin"`. On HTTP `409`, refresh setup status and switch to login.

- [ ] **Step 4: Run auth tests and full frontend suite**

Run:

```bash
cd frontend
npx vitest run src/__tests__/auth.test.tsx
npm test
npm run build
```

Expected: auth tests and full suite pass; production build exits `0`.

- [ ] **Step 5: Commit first-run UI**

```bash
git add frontend/src/pages/LoginPage.tsx frontend/src/__tests__/auth.test.tsx
git commit -m "feat(frontend): add first-run administrator setup"
```

### Task 6: Documentation and Full Verification

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update setup documentation**

Document:

```bash
cd backend
cp .env.example .env
python scripts/init_db.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

State that there is no default password, the first `/login` visit creates the administrator, and public registration closes afterward.

Replace invalid `APP_SECRET_KEY=test-key` test examples with:

```bash
APP_SECRET_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= python -m pytest tests -q
```

- [ ] **Step 2: Run backend verification**

Run:

```bash
cd backend
APP_SECRET_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= \
  python -m pytest tests -q
```

Expected: bootstrap-related tests pass. Any pre-existing unrelated failures must be reported separately and not hidden.

- [ ] **Step 3: Run frontend verification**

Run:

```bash
cd frontend
npm test
npm run build
```

Expected: all tests pass and build exits `0`.

- [ ] **Step 4: Run repository hygiene checks**

Run:

```bash
git diff --check
git grep -n "admin123\\|DEFAULT_PASSWORD\\|/api/admin/login\\|/api/auth/register" \
  -- backend frontend README.md CLAUDE.md
```

Expected: no production reference to the default password or removed endpoints; only intentional legacy-detection test/service constants may reference `admin123`.

- [ ] **Step 5: Commit documentation**

```bash
git add README.md CLAUDE.md
git commit -m "docs: document secure first-run setup"
```
