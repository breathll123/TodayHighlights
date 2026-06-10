# AI Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a generic AI enrichment layer for 今日看点, enabled first for the stocks topic, with encrypted model configs, item-level enrichment, topic-level AI daily highlights, admin visibility, and public-page presentation.

**Architecture:** Add focused AI domain models and services instead of expanding `highlights` into a generation audit table. `ai_item_enrichments` and `ai_topic_summaries` preserve generation state and traceability; successful item enrichment synchronizes into existing `highlights` so current public/admin display paths remain useful. The first enabled topic is stocks, while table and service boundaries are topic-aware for later AI/football expansion.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Alembic, MySQL/SQLite tests, Pydantic, existing Fernet `CryptoService`, React 18, Vite, TypeScript, Tailwind, shadcn/ui, TanStack Query, Vitest.

---

## File Structure

Create backend AI domain files:

- `backend/app/services/ai_models.py` manages encrypted model configs and default model invariants.
- `backend/app/services/ai_client.py` calls OpenAI-compatible chat completions and supports injected mock post functions.
- `backend/app/services/ai_prompts.py` stores item and topic prompt builders.
- `backend/app/services/ai_validation.py` validates model JSON output and enforces length/range limits.
- `backend/app/services/ai_enrichment.py` implements deterministic candidate selection, item enrichment, highlight sync, retry handling, topic summary generation, and job logging.

Modify backend integration points:

- `backend/app/models/entities.py` adds `AIModelConfig`, `AIItemEnrichment`, `AITopicSummary`, and `AIGenerationJob`.
- `backend/migrations/versions/20260605_0006_ai_enrichment.py` creates AI tables.
- `backend/app/schemas/admin.py` adds admin DTOs for AI models and jobs.
- `backend/app/schemas/public.py` adds public DTOs for topic AI summaries.
- `backend/app/api/admin.py` adds AI model, AI job, and manual regeneration endpoints.
- `backend/app/api/public.py` adds `GET /api/public/topics/{slug}/ai-summary`.
- `backend/app/services/jobs.py` replaces the old inline `_generate_highlights` path with the new AI item enrichment path when `source.enable_highlight` is true.
- `backend/app/services/summarizer.py` remains for backward compatibility until no tests or code paths import it.

Create or modify backend tests:

- `backend/tests/test_ai_models.py`
- `backend/tests/test_ai_validation.py`
- `backend/tests/test_ai_enrichment.py`
- `backend/tests/test_ai_admin_api.py`
- `backend/tests/test_ai_public_api.py`
- `backend/tests/test_jobs_ai_integration.py`

Create frontend files:

- `frontend/src/components/layout/AITopicSummary.tsx` renders the stock-page top AI daily highlights module.
- `frontend/src/pages/AdminAIJobsPage.tsx` renders lightweight AI generation logs and retry controls.

Modify frontend files:

- `frontend/src/api/types.ts` adds AI model, AI job, enrichment, and topic summary types.
- `frontend/src/api/client.ts` adds AI admin/public API functions.
- `frontend/src/pages/AdminSettingsPage.tsx` upgrades from a single model form to model config list plus form.
- `frontend/src/pages/TopicPage.tsx` fetches and renders stock AI summary above page blocks.
- `frontend/src/components/layout/NewsTimeline.tsx` accepts optional AI enrichment metadata for timeline rows.
- `frontend/src/components/layout/BlockCard.tsx` accepts optional AI enrichment metadata for card rows.
- `frontend/src/components/layout/GridRenderer.tsx` maps item AI fields into timeline/card components.
- `frontend/src/App.tsx` registers `/admin/ai-jobs`.
- `frontend/src/components/admin/AdminSidebar.tsx` adds an AI jobs navigation item.

Create or modify frontend tests:

- `frontend/src/__tests__/admin-ai-models.test.tsx`
- `frontend/src/__tests__/ai-topic-summary.test.tsx`
- `frontend/src/__tests__/ai-jobs-page.test.tsx`
- `frontend/src/__tests__/public-pages.test.tsx`
- `frontend/src/__tests__/match-list.test.tsx` only if shared rendering helpers need updates.

## Task 1: Add AI Persistence Models and Migration

**Files:**
- Modify: `backend/app/models/entities.py`
- Create: `backend/migrations/versions/20260605_0006_ai_enrichment.py`
- Test: `backend/tests/test_ai_models.py`

- [ ] **Step 1: Write failing model metadata tests**

Add `backend/tests/test_ai_models.py`:

```python
from sqlalchemy import inspect

from app.core.database import Base, get_session
from app.models.entities import AIGenerationJob, AIItemEnrichment, AIModelConfig, AITopicSummary


def test_ai_tables_are_registered() -> None:
    assert AIModelConfig.__tablename__ in Base.metadata.tables
    assert AIItemEnrichment.__tablename__ in Base.metadata.tables
    assert AITopicSummary.__tablename__ in Base.metadata.tables
    assert AIGenerationJob.__tablename__ in Base.metadata.tables


def test_ai_item_enrichment_retry_columns_exist(client) -> None:
    session = next(client.app.dependency_overrides[get_session]())
    columns = {column.name for column in inspect(session.bind).get_columns("ai_item_enrichments")}
    assert {"retry_count", "last_attempted_at", "error_message", "status"}.issubset(columns)


def test_ai_topic_summaries_version_column_exists(client) -> None:
    session = next(client.app.dependency_overrides[get_session]())
    columns = {column.name for column in inspect(session.bind).get_columns("ai_topic_summaries")}
    assert {"topic_id", "summary_date", "version", "items_json", "status"}.issubset(columns)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && APP_SECRET_KEY=test-key python -m pytest tests/test_ai_models.py -v`

Expected: FAIL because `AIModelConfig`, `AIItemEnrichment`, `AITopicSummary`, and `AIGenerationJob` are not defined.

- [ ] **Step 3: Add SQLAlchemy models**

Modify `backend/app/models/entities.py` by adding these classes after `Highlight` and before `AppSetting`:

```python
class AIModelConfig(TimestampMixin, Base):
    __tablename__ = "ai_model_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    model: Mapped[str] = mapped_column(String(160), nullable=False)
    api_key_encrypted: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)


class AIItemEnrichment(TimestampMixin, Base):
    __tablename__ = "ai_item_enrichments"
    __table_args__ = (
        UniqueConstraint("raw_item_id", name="uq_ai_item_enrichment_raw_item"),
        Index("ix_ai_item_enrichments_topic_status", "topic_id", "status", "importance_score"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), nullable=False)
    raw_item_id: Mapped[int] = mapped_column(ForeignKey("raw_items.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    generated_title: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    tags_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    related_symbols_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    importance_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    focus_points_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    risk_points_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    model_config_id: Mapped[int | None] = mapped_column(ForeignKey("ai_model_configs.id"))
    generated_by_model: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_attempted_at: Mapped[datetime | None] = mapped_column(DateTime)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime)


class AITopicSummary(TimestampMixin, Base):
    __tablename__ = "ai_topic_summaries"
    __table_args__ = (
        UniqueConstraint("topic_id", "summary_date", "version", name="uq_ai_topic_summary_version"),
        Index("ix_ai_topic_summaries_topic_status", "topic_id", "status", "summary_date", "version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), nullable=False)
    summary_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="generated", nullable=False)
    title: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    items_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    source_refs_json: Mapped[list[int]] = mapped_column(JSON, default=list, nullable=False)
    model_config_id: Mapped[int | None] = mapped_column(ForeignKey("ai_model_configs.id"))
    generated_by_model: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime)


class AIGenerationJob(Base):
    __tablename__ = "ai_generation_jobs"
    __table_args__ = (
        Index("ix_ai_generation_jobs_created", "created_at"),
        Index("ix_ai_generation_jobs_status", "status", "job_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_type: Mapped[str] = mapped_column(String(40), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(40), nullable=False)
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id"))
    raw_item_id: Mapped[int | None] = mapped_column(ForeignKey("raw_items.id"))
    item_enrichment_id: Mapped[int | None] = mapped_column(ForeignKey("ai_item_enrichments.id"))
    topic_summary_id: Mapped[int | None] = mapped_column(ForeignKey("ai_topic_summaries.id"))
    model_config_id: Mapped[int | None] = mapped_column(ForeignKey("ai_model_configs.id"))
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    input_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    retry_of_job_id: Mapped[int | None] = mapped_column(ForeignKey("ai_generation_jobs.id"))
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    log_excerpt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
```

- [ ] **Step 4: Add Alembic migration**

Create `backend/migrations/versions/20260605_0006_ai_enrichment.py` with `upgrade()` creating the four tables above and matching indexes/constraints. Use `sa.JSON()` for JSON columns and `sa.Text()` for encrypted API keys and log excerpts. `downgrade()` must drop tables in this order: `ai_generation_jobs`, `ai_topic_summaries`, `ai_item_enrichments`, `ai_model_configs`.

- [ ] **Step 5: Run model tests**

Run: `cd backend && APP_SECRET_KEY=test-key python -m pytest tests/test_ai_models.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/entities.py backend/migrations/versions/20260605_0006_ai_enrichment.py backend/tests/test_ai_models.py
git commit -m "feat(ai): add enrichment persistence models"
```

## Task 2: Add Encrypted AI Model Config Service and Admin API

**Files:**
- Create: `backend/app/services/ai_models.py`
- Modify: `backend/app/schemas/admin.py`
- Modify: `backend/app/api/admin.py`
- Test: `backend/tests/test_ai_admin_api.py`

- [ ] **Step 1: Write failing API tests**

Create `backend/tests/test_ai_admin_api.py`:

```python
from fastapi.testclient import TestClient


def test_create_ai_model_encrypts_key_and_hides_secret(client: TestClient) -> None:
    response = client.post(
        "/api/admin/ai-models",
        json={
            "name": "DeepSeek 默认",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
            "api_key": "secret-key",
            "is_default": True,
            "enabled": True,
            "notes": "stocks",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "DeepSeek 默认"
    assert data["has_api_key"] is True
    assert "api_key" not in data


def test_only_one_default_ai_model(client: TestClient) -> None:
    first = client.post(
        "/api/admin/ai-models",
        json={"name": "A", "base_url": "https://a.example/v1", "model": "a", "api_key": "a", "is_default": True, "enabled": True, "notes": ""},
    )
    second = client.post(
        "/api/admin/ai-models",
        json={"name": "B", "base_url": "https://b.example/v1", "model": "b", "api_key": "b", "is_default": True, "enabled": True, "notes": ""},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    listed = client.get("/api/admin/ai-models").json()
    defaults = [item["name"] for item in listed if item["is_default"]]
    assert defaults == ["B"]
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd backend && APP_SECRET_KEY=test-key python -m pytest tests/test_ai_admin_api.py -v`

Expected: FAIL with 404 for `/api/admin/ai-models`.

- [ ] **Step 3: Add Pydantic schemas**

Modify `backend/app/schemas/admin.py`:

```python
class AIModelConfigWrite(BaseModel):
    name: str
    base_url: str
    model: str
    api_key: str = ""
    is_default: bool = False
    enabled: bool = True
    notes: str = ""


class AIModelConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    base_url: str
    model: str
    is_default: bool
    enabled: bool
    notes: str
    has_api_key: bool
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 4: Add service functions**

Create `backend/app/services/ai_models.py`:

```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import CryptoService
from app.models.entities import AIModelConfig
from app.schemas.admin import AIModelConfigWrite


def _crypto() -> CryptoService:
    return CryptoService(settings.app_secret_key)


def _unset_other_defaults(session: Session, keep_id: int | None = None) -> None:
    for model in session.scalars(select(AIModelConfig).where(AIModelConfig.is_default.is_(True))):
        if keep_id is None or model.id != keep_id:
            model.is_default = False


def serialize_ai_model(model: AIModelConfig) -> dict:
    return {
        "id": model.id,
        "name": model.name,
        "base_url": model.base_url,
        "model": model.model,
        "is_default": model.is_default,
        "enabled": model.enabled,
        "notes": model.notes,
        "has_api_key": bool(model.api_key_encrypted),
        "created_at": model.created_at,
        "updated_at": model.updated_at,
    }


def list_ai_models(session: Session) -> list[AIModelConfig]:
    return list(session.scalars(select(AIModelConfig).order_by(AIModelConfig.is_default.desc(), AIModelConfig.id.desc())))


def get_default_ai_model(session: Session) -> AIModelConfig | None:
    return session.scalar(select(AIModelConfig).where(AIModelConfig.enabled.is_(True), AIModelConfig.is_default.is_(True)))


def create_ai_model(session: Session, payload: AIModelConfigWrite) -> AIModelConfig:
    if payload.is_default:
        _unset_other_defaults(session)
    model = AIModelConfig(
        name=payload.name,
        base_url=payload.base_url.rstrip("/"),
        model=payload.model,
        api_key_encrypted=_crypto().encrypt(payload.api_key),
        is_default=payload.is_default,
        enabled=payload.enabled,
        notes=payload.notes,
    )
    session.add(model)
    session.flush()
    return model


def update_ai_model(session: Session, model_id: int, payload: AIModelConfigWrite) -> AIModelConfig:
    model = session.get(AIModelConfig, model_id)
    if model is None:
        raise ValueError("AI model config not found")
    if payload.is_default:
        _unset_other_defaults(session, keep_id=model.id)
    model.name = payload.name
    model.base_url = payload.base_url.rstrip("/")
    model.model = payload.model
    if payload.api_key:
        model.api_key_encrypted = _crypto().encrypt(payload.api_key)
    model.is_default = payload.is_default
    model.enabled = payload.enabled
    model.notes = payload.notes
    session.flush()
    return model


def set_default_ai_model(session: Session, model_id: int) -> AIModelConfig:
    model = session.get(AIModelConfig, model_id)
    if model is None:
        raise ValueError("AI model config not found")
    _unset_other_defaults(session, keep_id=model.id)
    model.is_default = True
    model.enabled = True
    session.flush()
    return model
```

- [ ] **Step 5: Add admin endpoints**

Modify `backend/app/api/admin.py` imports and add endpoints before legacy `/settings/model`:

```python
from app.models.entities import AIModelConfig
from app.schemas.admin import AIModelConfigWrite
from app.services.ai_models import create_ai_model, list_ai_models, serialize_ai_model, set_default_ai_model, update_ai_model


@router.get("/ai-models")
def list_admin_ai_models(session: Session = Depends(get_session)) -> list[dict]:
    return [serialize_ai_model(model) for model in list_ai_models(session)]


@router.post("/ai-models")
def create_admin_ai_model(payload: AIModelConfigWrite, session: Session = Depends(get_session)) -> dict:
    model = create_ai_model(session, payload)
    session.commit()
    session.refresh(model)
    return serialize_ai_model(model)


@router.put("/ai-models/{model_id}")
def update_admin_ai_model(model_id: int, payload: AIModelConfigWrite, session: Session = Depends(get_session)) -> dict:
    try:
        model = update_ai_model(session, model_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session.commit()
    session.refresh(model)
    return serialize_ai_model(model)


@router.post("/ai-models/{model_id}/set-default")
def set_admin_ai_model_default(model_id: int, session: Session = Depends(get_session)) -> dict:
    try:
        model = set_default_ai_model(session, model_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session.commit()
    session.refresh(model)
    return serialize_ai_model(model)
```

- [ ] **Step 6: Run tests**

Run: `cd backend && APP_SECRET_KEY=test-key python -m pytest tests/test_ai_admin_api.py -v`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/ai_models.py backend/app/schemas/admin.py backend/app/api/admin.py backend/tests/test_ai_admin_api.py
git commit -m "feat(ai): add encrypted model config API"
```

## Task 3: Add AI Prompt, Client, and Output Validation

**Files:**
- Create: `backend/app/services/ai_client.py`
- Create: `backend/app/services/ai_prompts.py`
- Create: `backend/app/services/ai_validation.py`
- Test: `backend/tests/test_ai_validation.py`

- [ ] **Step 1: Write validation tests**

Create `backend/tests/test_ai_validation.py`:

```python
import pytest

from app.services.ai_validation import validate_item_enrichment_payload, validate_topic_summary_payload


def test_validate_item_enrichment_payload_accepts_valid_json() -> None:
    result = validate_item_enrichment_payload(
        {
            "title": "资金关注新能源",
            "summary": "新能源板块出现资金关注，相关公告和快讯密集出现。",
            "tags": ["资金", "新能源"],
            "related_symbols": ["新能源"],
            "importance_score": 72,
            "focus_points": ["资金关注度提升"],
            "risk_points": ["短期波动仍需观察"],
        }
    )

    assert result.importance_score == 72
    assert result.tags == ["资金", "新能源"]


def test_validate_item_enrichment_payload_rejects_score_out_of_range() -> None:
    with pytest.raises(ValueError, match="importance_score"):
        validate_item_enrichment_payload(
            {
                "title": "资金关注新能源",
                "summary": "新能源板块出现资金关注，相关公告和快讯密集出现。",
                "tags": ["资金"],
                "related_symbols": [],
                "importance_score": 101,
                "focus_points": ["资金关注度提升"],
                "risk_points": [],
            }
        )


def test_validate_topic_summary_requires_three_to_five_items() -> None:
    with pytest.raises(ValueError, match="items"):
        validate_topic_summary_payload({"title": "股票今日看点", "items": []})
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd backend && APP_SECRET_KEY=test-key python -m pytest tests/test_ai_validation.py -v`

Expected: FAIL because `app.services.ai_validation` does not exist.

- [ ] **Step 3: Implement validators**

Create `backend/app/services/ai_validation.py` with dataclasses:

```python
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ItemEnrichmentResult:
    title: str
    summary: str
    tags: list[str]
    related_symbols: list[str]
    importance_score: int
    focus_points: list[str]
    risk_points: list[str]


@dataclass(frozen=True)
class TopicSummaryItem:
    title: str
    reason: str
    related: list[str]
    risk: str
    source_refs: list[int]


@dataclass(frozen=True)
class TopicSummaryResult:
    title: str
    items: list[TopicSummaryItem]


def _require_str(value: Any, field: str, min_len: int, max_len: int) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    stripped = value.strip()
    if len(stripped) < min_len or len(stripped) > max_len:
        raise ValueError(f"{field} length must be {min_len}-{max_len}")
    return stripped


def _str_list(value: Any, field: str, max_items: int, item_max_len: int, min_items: int = 0) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    if len(value) < min_items or len(value) > max_items:
        raise ValueError(f"{field} length must be {min_items}-{max_items}")
    return [_require_str(item, field, 1, item_max_len) for item in value]


def validate_item_enrichment_payload(payload: dict[str, Any]) -> ItemEnrichmentResult:
    score = payload.get("importance_score")
    if not isinstance(score, int) or score < 0 or score > 100:
        raise ValueError("importance_score must be an integer from 0 to 100")
    return ItemEnrichmentResult(
        title=_require_str(payload.get("title"), "title", 1, 60),
        summary=_require_str(payload.get("summary"), "summary", 20, 180),
        tags=_str_list(payload.get("tags"), "tags", 5, 12),
        related_symbols=_str_list(payload.get("related_symbols"), "related_symbols", 10, 20),
        importance_score=score,
        focus_points=_str_list(payload.get("focus_points"), "focus_points", 3, 80, min_items=1),
        risk_points=_str_list(payload.get("risk_points"), "risk_points", 3, 80),
    )


def validate_topic_summary_payload(payload: dict[str, Any]) -> TopicSummaryResult:
    raw_items = payload.get("items")
    if not isinstance(raw_items, list) or len(raw_items) < 3 or len(raw_items) > 5:
        raise ValueError("items length must be 3-5")
    items = [
        TopicSummaryItem(
            title=_require_str(item.get("title"), "items.title", 1, 60),
            reason=_require_str(item.get("reason"), "items.reason", 20, 120),
            related=_str_list(item.get("related"), "items.related", 8, 20),
            risk=_require_str(item.get("risk", ""), "items.risk", 0, 100),
            source_refs=[int(ref) for ref in item.get("source_refs", [])[:10]],
        )
        for item in raw_items
    ]
    return TopicSummaryResult(title=_require_str(payload.get("title"), "title", 1, 40), items=items)
```

- [ ] **Step 4: Add prompt builders**

Create `backend/app/services/ai_prompts.py`:

```python
ITEM_SYSTEM_PROMPT = (
    "你是今日看点的股票信息整理助手。你的任务是把输入内容整理成中性、可读、可追溯的信息摘要。"
    "你可以说明事件、影响解读、关注点和风险提示。"
    "你必须避免买入、卖出、持有等操作建议，避免价格预测和涨跌预测，避免“必然”“确定”“强烈推荐”等确定性表达。"
    "只输出合法 JSON，不输出 Markdown，不输出额外解释。"
)

TOPIC_SYSTEM_PROMPT = (
    "你是今日看点的股票今日看点编辑助手。你的任务是从已加工摘要和市场异动上下文中提炼 3 到 5 条今日重点。"
    "你可以做影响解读和风险提示，但不能输出买卖建议、价格预测、涨跌预测或确定性投资结论。"
    "每条看点都应说明为什么重要，并保留引用来源 ID。"
    "只输出合法 JSON，不输出 Markdown，不输出额外解释。"
)


def item_user_prompt(*, title: str, source_name: str, published_at: str, body: str) -> str:
    return (
        "请基于以下股票主题内容生成结构化摘要。\n\n"
        "输出字段：title, summary, tags, related_symbols, importance_score, focus_points, risk_points。\n\n"
        f"标题：{title}\n来源：{source_name}\n发布时间：{published_at}\n正文：{body[:4000]}"
    )


def topic_user_prompt(context_json: str) -> str:
    return (
        "请基于以下股票主题上下文生成今日看点。\n\n"
        "输入包含：单条 AI 加工结果列表和榜单/行情异动列表。\n"
        "输出字段：title, items。\n\n"
        f"上下文：\n{context_json}"
    )
```

- [ ] **Step 5: Add OpenAI-compatible client**

Create `backend/app/services/ai_client.py`:

```python
import json
from collections.abc import Awaitable, Callable

import httpx

PostJson = Callable[[dict], Awaitable[dict]]


class AIClient:
    def __init__(self, base_url: str, api_key: str, model: str, post_json: PostJson | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self._post_json = post_json

    async def complete_json(self, system_prompt: str, user_prompt: str) -> dict:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        response = await self._send(payload)
        content = response["choices"][0]["message"]["content"]
        return json.loads(content)

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

- [ ] **Step 6: Run validation tests**

Run: `cd backend && APP_SECRET_KEY=test-key python -m pytest tests/test_ai_validation.py -v`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/ai_client.py backend/app/services/ai_prompts.py backend/app/services/ai_validation.py backend/tests/test_ai_validation.py
git commit -m "feat(ai): add prompt client and output validation"
```

## Task 4: Add Candidate Selection and Item Enrichment Service

**Files:**
- Create: `backend/app/services/ai_enrichment.py`
- Test: `backend/tests/test_ai_enrichment.py`

- [ ] **Step 1: Write candidate and enrichment tests**

Create `backend/tests/test_ai_enrichment.py` with tests for:

```python
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.database import get_session
from app.models.entities import AIItemEnrichment, RawItem, Source, Topic
from app.services.ai_enrichment import select_item_candidates


def _stock_source(session: Session) -> Source:
    topic = Topic(name="股票", slug="stocks", sort_order=1, enabled=True)
    session.add(topic)
    session.flush()
    source = Source(topic_id=topic.id, site="tonghuashun", name="同花顺", entry_url="https://example.com", enabled=True)
    session.add(source)
    session.flush()
    return source


def test_select_item_candidates_skips_short_content(client) -> None:
    session = next(client.app.dependency_overrides[get_session]())
    source = _stock_source(session)
    raw = RawItem(
        source_id=source.id,
        external_id="short",
        url="https://example.com/1",
        title="短",
        body="很短",
        published_at=datetime.utcnow(),
        metrics_json={},
        content_hash="short-hash",
    )
    session.add(raw)
    session.commit()

    assert select_item_candidates(session, source.topic_id, [raw], limit=50) == []


def test_select_item_candidates_skips_existing_enrichment(client) -> None:
    session = next(client.app.dependency_overrides[get_session]())
    source = _stock_source(session)
    raw = RawItem(
        source_id=source.id,
        external_id="ok",
        url="https://example.com/ok",
        title="新能源公告密集发布",
        body="新能源板块相关公司公告密集发布，市场关注度提升。",
        published_at=datetime.utcnow(),
        metrics_json={},
        content_hash="ok-hash",
    )
    session.add(raw)
    session.flush()
    session.add(AIItemEnrichment(topic_id=source.topic_id, raw_item_id=raw.id, status="generated"))
    session.commit()

    assert select_item_candidates(session, source.topic_id, [raw], limit=50) == []


def test_select_item_candidates_uses_24_hour_window(client) -> None:
    session = next(client.app.dependency_overrides[get_session]())
    source = _stock_source(session)
    old = RawItem(
        source_id=source.id,
        external_id="old",
        url="https://example.com/old",
        title="旧公告内容达到长度",
        body="这是一条超过长度下限但已经超过二十四小时的股票资讯内容。",
        published_at=datetime.utcnow() - timedelta(hours=25),
        metrics_json={},
        content_hash="old-hash",
    )
    recent = RawItem(
        source_id=source.id,
        external_id="recent",
        url="https://example.com/recent",
        title="近期公告内容达到长度",
        body="这是一条超过长度下限并且仍在二十四小时窗口内的股票资讯内容。",
        published_at=datetime.utcnow(),
        metrics_json={},
        content_hash="recent-hash",
    )
    session.add_all([old, recent])
    session.commit()

    candidates = select_item_candidates(session, source.topic_id, [old, recent], limit=50)
    assert [item.external_id for item in candidates] == ["recent"]
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd backend && APP_SECRET_KEY=test-key python -m pytest tests/test_ai_enrichment.py -v`

Expected: FAIL because `select_item_candidates` is not defined.

- [ ] **Step 3: Implement deterministic candidate selection**

Create `backend/app/services/ai_enrichment.py` with constants:

```python
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import AIItemEnrichment, RawItem

ITEM_WINDOW_HOURS = 24
MIN_TITLE_CHARS = 6
MIN_CONTENT_CHARS = 40
CRAWL_ITEM_LIMIT = 50
BACKFILL_ITEM_LIMIT = 200


def _normalized_title(title: str) -> str:
    return "".join(title.split()).lower()


def _published_or_created(raw_item: RawItem) -> datetime:
    return raw_item.published_at or raw_item.created_at


def select_item_candidates(session: Session, topic_id: int, raw_items: list[RawItem], *, limit: int) -> list[RawItem]:
    cutoff = datetime.utcnow() - timedelta(hours=ITEM_WINDOW_HOURS)
    raw_ids = [item.id for item in raw_items if item.id is not None]
    existing_ids = set(
        session.scalars(select(AIItemEnrichment.raw_item_id).where(AIItemEnrichment.raw_item_id.in_(raw_ids))).all()
    )
    seen_titles: set[str] = set()
    candidates: list[RawItem] = []
    for item in sorted(raw_items, key=_published_or_created, reverse=True):
        if item.id in existing_ids:
            continue
        if _published_or_created(item) < cutoff:
            continue
        title = item.title.strip()
        body = item.body.strip()
        if len(title) < MIN_TITLE_CHARS:
            continue
        if len(" ".join((title, body)).strip()) < MIN_CONTENT_CHARS:
            continue
        title_key = _normalized_title(title)
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)
        candidates.append(item)
        if len(candidates) >= limit:
            break
    return candidates
```

- [ ] **Step 4: Add item enrichment service skeleton**

Extend `backend/app/services/ai_enrichment.py` with `create_pending_enrichments(session, topic_id, raw_items)` that creates `AIItemEnrichment(status="pending")` records for selected candidates and returns them. Keep model calls for Task 5.

- [ ] **Step 5: Run tests**

Run: `cd backend && APP_SECRET_KEY=test-key python -m pytest tests/test_ai_enrichment.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/ai_enrichment.py backend/tests/test_ai_enrichment.py
git commit -m "feat(ai): add stock enrichment candidate selection"
```

## Task 5: Process Item Enrichments, Sync Highlights, and Log Jobs

**Files:**
- Modify: `backend/app/services/ai_enrichment.py`
- Modify: `backend/app/services/jobs.py`
- Test: `backend/tests/test_jobs_ai_integration.py`

- [ ] **Step 1: Write integration tests**

Create `backend/tests/test_jobs_ai_integration.py` with a focused service-level test that inserts a stock topic, source, raw item, default AI model config, and fake AI post response. Assert that `process_pending_item_enrichment(...)` creates `AIItemEnrichment(status="generated")`, creates one `Highlight`, sets `generated_by_model`, and creates `AIGenerationJob(status="succeeded")`.

Use a fake payload response:

```python
FAKE_ITEM_RESPONSE = {
    "choices": [
        {
            "message": {
                "content": "{\"title\":\"资金关注新能源\",\"summary\":\"新能源相关公告密集发布，市场关注度有所提升。\",\"tags\":[\"新能源\",\"公告\"],\"related_symbols\":[\"新能源\"],\"importance_score\":72,\"focus_points\":[\"公告密集发布\"],\"risk_points\":[\"短期波动仍需观察\"]}"
            }
        }
    ]
}
```

- [ ] **Step 2: Run test to verify failure**

Run: `cd backend && APP_SECRET_KEY=test-key python -m pytest tests/test_jobs_ai_integration.py -v`

Expected: FAIL because item processing functions do not exist.

- [ ] **Step 3: Implement processing functions**

Extend `backend/app/services/ai_enrichment.py` with:

- `process_item_enrichment(session, enrichment_id, post_json=None, trigger_type="crawl", retry_of_job_id=None)`
- `sync_highlight_from_enrichment(session, enrichment)`
- `retry_item_enrichment(session, job_id, post_json=None)`

Required behavior:

- Set enrichment `status="processing"` before model call.
- Increment `retry_count` only when `trigger_type == "retry"`.
- Update `last_attempted_at` before model call.
- Reject retry when `retry_count >= 3`.
- Use `get_default_ai_model(session)`.
- Decrypt model API key with `CryptoService`.
- Call `AIClient.complete_json(...)`.
- Validate with `validate_item_enrichment_payload(...)`.
- Save generated fields.
- Set `status="generated"`, `generated_at`, and `generated_by_model`.
- Create or update one `Highlight` for the same `raw_item_id`.
- Create `AIGenerationJob` for success or failure.

- [ ] **Step 4: Replace old inline highlight path**

Modify `backend/app/services/jobs.py`:

- Keep `save_raw_items(...)`.
- If `source.enable_highlight` is true, call `create_pending_enrichments(session, source.topic_id, raw_items)` and then process each created enrichment.
- Remove `_generate_highlights(...)` usage from `run_crawl_job`.
- Keep fallback behavior through failed AI jobs and raw content display; do not create fallback highlights from failed AI calls.

- [ ] **Step 5: Run integration tests**

Run: `cd backend && APP_SECRET_KEY=test-key python -m pytest tests/test_jobs_ai_integration.py tests/test_ai_enrichment.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/ai_enrichment.py backend/app/services/jobs.py backend/tests/test_jobs_ai_integration.py
git commit -m "feat(ai): process item enrichments into highlights"
```

## Task 6: Add Topic Summary Generation and Public API

**Files:**
- Modify: `backend/app/services/ai_enrichment.py`
- Modify: `backend/app/schemas/public.py`
- Modify: `backend/app/api/public.py`
- Modify: `backend/app/api/admin.py`
- Test: `backend/tests/test_ai_public_api.py`

- [ ] **Step 1: Write public API tests**

Create `backend/tests/test_ai_public_api.py`:

```python
from datetime import datetime

from fastapi.testclient import TestClient

from app.core.database import get_session
from app.models.entities import AITopicSummary, Topic


def test_public_ai_summary_returns_latest_generated_version(client: TestClient) -> None:
    session = next(client.app.dependency_overrides[get_session]())
    topic = Topic(name="股票", slug="stocks", sort_order=1, enabled=True)
    session.add(topic)
    session.flush()
    session.add_all(
        [
            AITopicSummary(topic_id=topic.id, summary_date=datetime(2026, 6, 5), version=1, status="generated", title="旧版", items_json=[{"title": "旧", "reason": "旧内容", "related": [], "risk": "", "source_refs": []}], source_refs_json=[]),
            AITopicSummary(topic_id=topic.id, summary_date=datetime(2026, 6, 5), version=2, status="generated", title="新版", items_json=[{"title": "新", "reason": "新版内容达到长度要求", "related": [], "risk": "", "source_refs": []}], source_refs_json=[]),
        ]
    )
    session.commit()

    response = client.get("/api/public/topics/stocks/ai-summary")

    assert response.status_code == 200
    assert response.json()["title"] == "新版"
    assert response.json()["version"] == 2


def test_public_ai_summary_404_when_missing(client: TestClient) -> None:
    response = client.get("/api/public/topics/stocks/ai-summary")
    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd backend && APP_SECRET_KEY=test-key python -m pytest tests/test_ai_public_api.py -v`

Expected: FAIL with 404 or missing route behavior.

- [ ] **Step 3: Add public schemas**

Modify `backend/app/schemas/public.py` with `AITopicSummaryItemRead` and `AITopicSummaryRead` DTOs matching `title`, `reason`, `related`, `risk`, `source_refs`, `version`, `generated_at`.

- [ ] **Step 4: Add public endpoint**

Modify `backend/app/api/public.py`:

- Import `AITopicSummary`.
- Query topic by slug.
- Query `AITopicSummary` where `topic_id`, `status == "generated"`, order by `summary_date.desc(), version.desc()`.
- Return 404 when no generated summary exists.

- [ ] **Step 5: Add manual regenerate endpoint**

Modify `backend/app/api/admin.py`:

```python
@router.post("/ai/topic-summaries/stocks/regenerate")
def regenerate_stocks_ai_summary(session: Session = Depends(get_session)) -> dict:
    summary = generate_topic_summary(session, topic_slug="stocks", trigger_type="manual")
    session.commit()
    return {"id": summary.id, "version": summary.version, "status": summary.status}
```

Implement `generate_topic_summary(...)` in `ai_enrichment.py` using latest 24-hour generated enrichments and top anomaly context. It must create a higher `version` for the same `summary_date` instead of overwriting.

- [ ] **Step 6: Run tests**

Run: `cd backend && APP_SECRET_KEY=test-key python -m pytest tests/test_ai_public_api.py -v`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/ai_enrichment.py backend/app/schemas/public.py backend/app/api/public.py backend/app/api/admin.py backend/tests/test_ai_public_api.py
git commit -m "feat(ai): add stock topic summary API"
```

## Task 7: Add AI Jobs Admin API and Retry Endpoint

**Files:**
- Modify: `backend/app/schemas/admin.py`
- Modify: `backend/app/api/admin.py`
- Test: `backend/tests/test_ai_admin_api.py`

- [ ] **Step 1: Extend admin API tests**

Add tests to `backend/tests/test_ai_admin_api.py`:

```python
def test_list_ai_jobs(client: TestClient) -> None:
    response = client.get("/api/admin/ai-jobs")
    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert response.json()["items"] == []


def test_retry_missing_ai_job_returns_404(client: TestClient) -> None:
    response = client.post("/api/admin/ai-jobs/999/retry")
    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd backend && APP_SECRET_KEY=test-key python -m pytest tests/test_ai_admin_api.py -v`

Expected: FAIL because `/api/admin/ai-jobs` is not implemented.

- [ ] **Step 3: Add admin schemas**

Add `AIJobRead` and `AIJobListResponse` to `backend/app/schemas/admin.py`.

- [ ] **Step 4: Add endpoints**

Modify `backend/app/api/admin.py`:

- `GET /api/admin/ai-jobs?page=1&page_size=20`
- `POST /api/admin/ai-jobs/{job_id}/retry`

The retry endpoint must call `retry_item_enrichment(...)`, return 404 for missing jobs, and return 400 if retry is not allowed because `retry_count >= 3`.

- [ ] **Step 5: Run tests**

Run: `cd backend && APP_SECRET_KEY=test-key python -m pytest tests/test_ai_admin_api.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/admin.py backend/app/api/admin.py backend/tests/test_ai_admin_api.py
git commit -m "feat(ai): add generation job admin API"
```

## Task 8: Upgrade Frontend API Types and Model Settings UI

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/pages/AdminSettingsPage.tsx`
- Test: `frontend/src/__tests__/admin-ai-models.test.tsx`

- [ ] **Step 1: Write failing frontend tests**

Create `frontend/src/__tests__/admin-ai-models.test.tsx` to mock `fetchAIModels`, `createAIModel`, `updateAIModel`, and assert:

- model list renders names and `has_api_key` state.
- create form submits `name`, `base_url`, `model`, `api_key`, `is_default`, `enabled`, `notes`.
- API Key input clears after successful save.

- [ ] **Step 2: Run test to verify failure**

Run: `cd frontend && npm test -- admin-ai-models.test.tsx`

Expected: FAIL because AI model API functions and model list UI are missing.

- [ ] **Step 3: Add types**

Add to `frontend/src/api/types.ts`:

```ts
export interface AIModelConfig {
  id: number;
  name: string;
  base_url: string;
  model: string;
  is_default: boolean;
  enabled: boolean;
  notes: string;
  has_api_key: boolean;
  created_at: string;
  updated_at: string;
}

export interface AIModelConfigWrite {
  name: string;
  base_url: string;
  model: string;
  api_key: string;
  is_default: boolean;
  enabled: boolean;
  notes: string;
}
```

- [ ] **Step 4: Add client functions**

Add to `frontend/src/api/client.ts`:

```ts
export function fetchAIModels(): Promise<AIModelConfig[]> {
  return api.get<AIModelConfig[]>("/api/admin/ai-models").then((r) => r.data);
}

export function createAIModel(data: AIModelConfigWrite): Promise<AIModelConfig> {
  return api.post<AIModelConfig>("/api/admin/ai-models", data).then((r) => r.data);
}

export function updateAIModel(id: number, data: AIModelConfigWrite): Promise<AIModelConfig> {
  return api.put<AIModelConfig>(`/api/admin/ai-models/${id}`, data).then((r) => r.data);
}

export function setDefaultAIModel(id: number): Promise<AIModelConfig> {
  return api.post<AIModelConfig>(`/api/admin/ai-models/${id}/set-default`).then((r) => r.data);
}
```

- [ ] **Step 5: Upgrade `AdminSettingsPage`**

Replace the single model form with:

- A compact list of AI model configs.
- A create/edit form with fields from `AIModelConfigWrite`.
- API Key placeholder: `已配置，留空则不修改`.
- Badges for `默认`, `启用`, and `API Key 已配置`.
- A `设为默认` button for non-default models.

- [ ] **Step 6: Run frontend test**

Run: `cd frontend && npm test -- admin-ai-models.test.tsx`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/api/types.ts frontend/src/api/client.ts frontend/src/pages/AdminSettingsPage.tsx frontend/src/__tests__/admin-ai-models.test.tsx
git commit -m "feat(ai): add model config settings UI"
```

## Task 9: Add Public AI Topic Summary UI

**Files:**
- Create: `frontend/src/components/layout/AITopicSummary.tsx`
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/pages/TopicPage.tsx`
- Test: `frontend/src/__tests__/ai-topic-summary.test.tsx`

- [ ] **Step 1: Write failing component tests**

Create `frontend/src/__tests__/ai-topic-summary.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AITopicSummary } from "@/components/layout/AITopicSummary";

describe("AITopicSummary", () => {
  it("renders generated stock highlights", () => {
    render(
      <AITopicSummary
        summary={{
          title: "股票今日看点",
          version: 2,
          generated_at: "2026-06-05T09:30:00",
          items: [
            { title: "新能源公告密集", reason: "公告数量增加，市场关注度提升。", related: ["新能源"], risk: "短期波动仍需观察", source_refs: [1] },
            { title: "资金关注主线", reason: "资金流入靠前的板块集中出现。", related: ["资金"], risk: "持续性需要跟踪", source_refs: [2] },
            { title: "龙虎榜活跃", reason: "部分个股成交额和买卖席位活跃。", related: ["龙虎榜"], risk: "个股风险较高", source_refs: [3] },
          ],
        }}
      />
    );

    expect(screen.getByText("股票今日看点")).toBeInTheDocument();
    expect(screen.getByText("AI 摘要，仅供信息参考")).toBeInTheDocument();
    expect(screen.getByText("新能源公告密集")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify failure**

Run: `cd frontend && npm test -- ai-topic-summary.test.tsx`

Expected: FAIL because `AITopicSummary` does not exist.

- [ ] **Step 3: Add public types and API**

Add `AITopicSummaryResponse` to `frontend/src/api/types.ts`, and `fetchAITopicSummary(slug: string)` to `frontend/src/api/client.ts`.

- [ ] **Step 4: Implement component**

Create `frontend/src/components/layout/AITopicSummary.tsx` with:

- Title row with `BrainCircuit` icon.
- 3-5 item rows.
- Related chips.
- Risk text.
- Generated time.
- Fixed disclaimer text: `AI 摘要，仅供信息参考`.
- Hidden render when `summary` is `null`.

- [ ] **Step 5: Render on stock topic only**

Modify `frontend/src/pages/TopicPage.tsx`:

- Derive `slug` from `/topics/{slug}`.
- If `slug === "stocks"`, call `useQuery(["ai-topic-summary", slug], () => fetchAITopicSummary(slug))`.
- On 404 or request error, render nothing.
- During loading, render a compact skeleton above `GridRenderer`.
- Render `AITopicSummary` above `GridRenderer` when data exists.

- [ ] **Step 6: Run tests**

Run: `cd frontend && npm test -- ai-topic-summary.test.tsx public-pages.test.tsx`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/layout/AITopicSummary.tsx frontend/src/api/types.ts frontend/src/api/client.ts frontend/src/pages/TopicPage.tsx frontend/src/__tests__/ai-topic-summary.test.tsx
git commit -m "feat(ai): show stock topic AI summary"
```

## Task 10: Add Item-Level AI Enhancement Display

**Files:**
- Modify: `frontend/src/components/layout/NewsTimeline.tsx`
- Modify: `frontend/src/components/layout/BlockCard.tsx`
- Modify: `frontend/src/components/layout/GridRenderer.tsx`
- Test: `frontend/src/__tests__/public-pages.test.tsx`

- [ ] **Step 1: Write failing display tests**

Extend `frontend/src/__tests__/public-pages.test.tsx` with assertions that a timeline/card item with:

```ts
ai_enrichment: {
  status: "generated",
  summary: "AI 生成的中性摘要。",
  tags: ["资金"],
  importance_score: 72,
}
```

renders the AI summary and tag, while the same item with `status: "failed"` or `importance_score: 39` does not render AI enhancement.

- [ ] **Step 2: Run tests to verify failure**

Run: `cd frontend && npm test -- public-pages.test.tsx`

Expected: FAIL because components ignore `ai_enrichment`.

- [ ] **Step 3: Add item type and rendering gate**

In `NewsTimeline.tsx` and `BlockCard.tsx`, add:

```ts
interface AIItemEnhancement {
  status: string;
  summary: string;
  tags: string[];
  importance_score: number;
}

function shouldShowAI(enrichment?: AIItemEnhancement) {
  return Boolean(enrichment && enrichment.status === "generated" && enrichment.importance_score >= 40);
}
```

Render AI summary and tags only when `shouldShowAI(...)` is true. Keep original title/body visible in all other states.

- [ ] **Step 4: Map enrichment fields from blocks**

Modify `frontend/src/components/layout/GridRenderer.tsx` so `BlockCard` and `NewsTimeline` receive `item.ai_enrichment` when the backend includes it.

- [ ] **Step 5: Run tests**

Run: `cd frontend && npm test -- public-pages.test.tsx`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/layout/NewsTimeline.tsx frontend/src/components/layout/BlockCard.tsx frontend/src/components/layout/GridRenderer.tsx frontend/src/__tests__/public-pages.test.tsx
git commit -m "feat(ai): show item-level enrichment on public blocks"
```

## Task 11: Add AI Jobs Admin Page

**Files:**
- Create: `frontend/src/pages/AdminAIJobsPage.tsx`
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/admin/AdminSidebar.tsx`
- Test: `frontend/src/__tests__/ai-jobs-page.test.tsx`

- [ ] **Step 1: Write failing admin page tests**

Create `frontend/src/__tests__/ai-jobs-page.test.tsx` asserting:

- page shows empty state when no jobs.
- failed job renders error excerpt and retry button.
- retry button calls `retryAIJob(job.id)`.

- [ ] **Step 2: Run test to verify failure**

Run: `cd frontend && npm test -- ai-jobs-page.test.tsx`

Expected: FAIL because the page and API functions do not exist.

- [ ] **Step 3: Add types and client functions**

Add `AIGenerationJob`, `AIJobListResponse`, `fetchAIJobs`, and `retryAIJob` to `frontend/src/api/types.ts` and `frontend/src/api/client.ts`.

- [ ] **Step 4: Implement page**

Create `frontend/src/pages/AdminAIJobsPage.tsx`:

- Use `fetchAIJobs(1, 20)`.
- Show job type, trigger type, status, success/failed counts, error message, started/finished time.
- Show retry button only for `status === "failed"`.
- On retry success, invalidate `["ai-jobs"]`.

- [ ] **Step 5: Register route and nav**

Modify `frontend/src/App.tsx`:

```tsx
<Route path="/admin/ai-jobs" element={<AdminAIJobsPage />} />
```

Modify `frontend/src/components/admin/AdminSidebar.tsx` to add an AI jobs link with `BrainCircuit` or `Sparkles`.

- [ ] **Step 6: Run tests**

Run: `cd frontend && npm test -- ai-jobs-page.test.tsx admin-pages.test.tsx`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/AdminAIJobsPage.tsx frontend/src/api/types.ts frontend/src/api/client.ts frontend/src/App.tsx frontend/src/components/admin/AdminSidebar.tsx frontend/src/__tests__/ai-jobs-page.test.tsx
git commit -m "feat(ai): add generation jobs admin page"
```

## Task 12: Full Verification and Browser QA

**Files:**
- No new source files unless verification exposes a defect.

- [ ] **Step 1: Run backend tests**

Run: `cd backend && APP_SECRET_KEY=test-key python -m pytest tests/ -v`

Expected: PASS.

- [ ] **Step 2: Run frontend tests**

Run: `cd frontend && npm test`

Expected: PASS.

- [ ] **Step 3: Run frontend build**

Run: `cd frontend && npm run build`

Expected: PASS. Existing Vite large chunk warning is acceptable if no new build failure appears.

- [ ] **Step 4: Run diff hygiene**

Run: `git diff --check`

Expected: no output.

- [ ] **Step 5: Browser QA**

Start backend and frontend using the repo's existing commands:

```bash
cd backend && APP_SECRET_KEY=test-key uvicorn app.main:app --reload
cd frontend && npm run dev
```

Inspect:

- `/admin/settings`: model list renders, create/edit form does not expose API key plaintext.
- `/admin/ai-jobs`: empty and failed-job states render.
- `/topics/stocks`: AI summary hidden when no generated data, original blocks still render.
- `/topics/stocks`: with seeded/generated summary, top AI module appears above blocks and does not create horizontal overflow.

- [ ] **Step 6: Final commit or fix commit**

If browser QA requires fixes, commit each fix with a scoped message such as:

```bash
git add frontend/src/components/layout/AITopicSummary.tsx frontend/src/pages/TopicPage.tsx
git commit -m "fix(ai): correct stock summary empty state"
```

If no fixes are required, do not create an empty commit.

## Self-Review Checklist

- Spec coverage:
  - Encrypted multi-model config: Tasks 1, 2, 8.
  - Item enrichment with retry fields and max retry: Tasks 1, 5, 7.
  - Topic summary versioning: Tasks 1, 6.
  - Generation job fields and retry logs: Tasks 1, 5, 7, 11.
  - Candidate filters and thresholds: Task 4.
  - Prompt and output validation: Task 3.
  - Public top summary and degradation: Tasks 6, 9.
  - Item-level display rules: Task 10.
  - Full tests and browser QA: Task 12.

- Placeholder scan:
  - The plan uses concrete filenames, commands, limits, and status values.
  - Any implementation worker should still inspect current imports after each task because files may have shifted from subsequent commits.

- Type consistency:
  - Backend status values use `pending`, `processing`, `generated`, `failed`, `hidden` for enrichment/summary and `pending`, `processing`, `succeeded`, `failed`, `partial` for jobs.
  - Frontend API type names match backend resource names: `AIModelConfig`, `AIGenerationJob`, `AITopicSummaryResponse`.
