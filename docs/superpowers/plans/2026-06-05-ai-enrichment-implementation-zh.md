# AI 赋能实施计划

> **给 Agentic Worker 的说明：** 必须使用的子技能：superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans，按任务逐步实施本计划。各步骤使用复选框（`- [ ]`）语法跟踪进度。

**目标：** 为今日看点构建通用 AI 赋能层，首批在股票主题启用，包含加密模型配置、单条内容加工、主题级 AI 今日看点、后台可见性以及公开页展示。

**架构：** 新增专注的 AI 领域模型和服务，而不是将 `highlights` 扩展为生成审计表。`ai_item_enrichments` 和 `ai_topic_summaries` 保留生成状态和追溯信息；单条内容加工成功后同步到现有 `highlights`，使当前公开页/后台展示路径继续可用。首批启用主题为股票，数据表和服务边界具备主题感知能力，便于后续扩展至 AI/足球主题。

**技术栈：** FastAPI、SQLAlchemy 2.0、Alembic、MySQL/SQLite 测试、Pydantic、现有 Fernet `CryptoService`、React 18、Vite、TypeScript、Tailwind、shadcn/ui、TanStack Query、Vitest。

---

## 文件结构

新增后端 AI 领域文件：

- `backend/app/services/ai_models.py`：管理加密模型配置和默认模型唯一性约束。
- `backend/app/services/ai_client.py`：调用 OpenAI 兼容的 chat completions 接口，支持注入 mock post 函数。
- `backend/app/services/ai_prompts.py`：存储单条和主题级的 Prompt 构建器。
- `backend/app/services/ai_validation.py`：校验模型 JSON 输出，强制执行长度/范围限制。
- `backend/app/services/ai_enrichment.py`：实现确定性候选筛选、单条加工、看点同步、重试处理、主题汇总生成和任务日志记录。

修改后端集成点：

- `backend/app/models/entities.py`：新增 `AIModelConfig`、`AIItemEnrichment`、`AITopicSummary`、`AIGenerationJob`。
- `backend/migrations/versions/20260605_0006_ai_enrichment.py`：创建 AI 相关数据表。
- `backend/app/schemas/admin.py`：新增 AI 模型和任务的管理端 DTO。
- `backend/app/schemas/public.py`：新增主题 AI 汇总的公开端 DTO。
- `backend/app/api/admin.py`：新增 AI 模型、AI 任务和手动重新生成接口。
- `backend/app/api/public.py`：新增 `GET /api/public/topics/{slug}/ai-summary`。
- `backend/app/services/jobs.py`：当 `source.enable_highlight` 为 true 时，用新的 AI 单条加工路径替换旧的内联 `_generate_highlights` 路径。
- `backend/app/services/summarizer.py`：保持向后兼容，直到无测试或代码路径引用为止。

新增或修改后端测试：

- `backend/tests/test_ai_models.py`
- `backend/tests/test_ai_validation.py`
- `backend/tests/test_ai_enrichment.py`
- `backend/tests/test_ai_admin_api.py`
- `backend/tests/test_ai_public_api.py`
- `backend/tests/test_jobs_ai_integration.py`

新增前端文件：

- `frontend/src/components/layout/AITopicSummary.tsx`：渲染股票页顶部的 AI 今日看点模块。
- `frontend/src/pages/AdminAIJobsPage.tsx`：渲染轻量 AI 生成日志和重试控制。

修改前端文件：

- `frontend/src/api/types.ts`：新增 AI 模型、AI 任务、加工结果和主题汇总类型。
- `frontend/src/api/client.ts`：新增 AI 管理端/公开端 API 函数。
- `frontend/src/pages/AdminSettingsPage.tsx`：将单模型表单升级为模型配置列表和表单。
- `frontend/src/pages/TopicPage.tsx`：在 page blocks 上方获取并渲染股票 AI 汇总。
- `frontend/src/components/layout/NewsTimeline.tsx`：接受可选的 AI 加工元数据用于时间轴行展示。
- `frontend/src/components/layout/BlockCard.tsx`：接受可选的 AI 加工元数据用于卡片行展示。
- `frontend/src/components/layout/GridRenderer.tsx`：将条目 AI 字段映射到时间轴/卡片组件。
- `frontend/src/App.tsx`：注册 `/admin/ai-jobs` 路由。
- `frontend/src/components/admin/AdminSidebar.tsx`：新增 AI 任务导航入口。

新增或修改前端测试：

- `frontend/src/__tests__/admin-ai-models.test.tsx`
- `frontend/src/__tests__/ai-topic-summary.test.tsx`
- `frontend/src/__tests__/ai-jobs-page.test.tsx`
- `frontend/src/__tests__/public-pages.test.tsx`
- `frontend/src/__tests__/match-list.test.tsx`：仅在共享渲染辅助函数需要更新时修改。

---

## 任务 1：新增 AI 持久化模型和数据库迁移

**涉及文件：**
- 修改：`backend/app/models/entities.py`
- 新增：`backend/migrations/versions/20260605_0006_ai_enrichment.py`
- 测试：`backend/tests/test_ai_models.py`

- [ ] **步骤 1：编写失败的模型元数据测试**

新增 `backend/tests/test_ai_models.py`：

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

- [ ] **步骤 2：运行测试，确认失败**

执行：`cd backend && APP_SECRET_KEY=test-key python -m pytest tests/test_ai_models.py -v`

预期：FAIL，因为 `AIModelConfig`、`AIItemEnrichment`、`AITopicSummary`、`AIGenerationJob` 尚未定义。

- [ ] **步骤 3：新增 SQLAlchemy 模型**

修改 `backend/app/models/entities.py`，在 `Highlight` 之后、`AppSetting` 之前新增如下类：

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

- [ ] **步骤 4：新增 Alembic 迁移**

创建 `backend/migrations/versions/20260605_0006_ai_enrichment.py`，`upgrade()` 方法创建上述四张表及对应索引/约束。JSON 列使用 `sa.JSON()`，加密 API Key 和日志摘要使用 `sa.Text()`。`downgrade()` 按以下顺序删表：`ai_generation_jobs`、`ai_topic_summaries`、`ai_item_enrichments`、`ai_model_configs`。

- [ ] **步骤 5：运行模型测试**

执行：`cd backend && APP_SECRET_KEY=test-key python -m pytest tests/test_ai_models.py -v`

预期：PASS。

- [ ] **步骤 6：提交**

```bash
git add backend/app/models/entities.py backend/migrations/versions/20260605_0006_ai_enrichment.py backend/tests/test_ai_models.py
git commit -m "feat(ai): add enrichment persistence models"
```

---

## 任务 2：新增加密 AI 模型配置服务和管理端 API

**涉及文件：**
- 新增：`backend/app/services/ai_models.py`
- 修改：`backend/app/schemas/admin.py`
- 修改：`backend/app/api/admin.py`
- 测试：`backend/tests/test_ai_admin_api.py`

- [ ] **步骤 1：编写失败的 API 测试**

创建 `backend/tests/test_ai_admin_api.py`：

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

- [ ] **步骤 2：运行测试，确认失败**

执行：`cd backend && APP_SECRET_KEY=test-key python -m pytest tests/test_ai_admin_api.py -v`

预期：FAIL，`/api/admin/ai-models` 返回 404。

- [ ] **步骤 3：新增 Pydantic Schema**

修改 `backend/app/schemas/admin.py`：

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

- [ ] **步骤 4：新增 Service 函数**

创建 `backend/app/services/ai_models.py`：

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

- [ ] **步骤 5：新增管理端接口**

修改 `backend/app/api/admin.py`，在 `/settings/model` 旧接口之前新增如下导入和端点：

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

- [ ] **步骤 6：运行测试**

执行：`cd backend && APP_SECRET_KEY=test-key python -m pytest tests/test_ai_admin_api.py -v`

预期：PASS。

- [ ] **步骤 7：提交**

```bash
git add backend/app/services/ai_models.py backend/app/schemas/admin.py backend/app/api/admin.py backend/tests/test_ai_admin_api.py
git commit -m "feat(ai): add encrypted model config API"
```

---

## 任务 3：新增 AI Prompt、客户端和输出校验

**涉及文件：**
- 新增：`backend/app/services/ai_client.py`
- 新增：`backend/app/services/ai_prompts.py`
- 新增：`backend/app/services/ai_validation.py`
- 测试：`backend/tests/test_ai_validation.py`

- [ ] **步骤 1：编写校验测试**

创建 `backend/tests/test_ai_validation.py`：

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

- [ ] **步骤 2：运行测试，确认失败**

执行：`cd backend && APP_SECRET_KEY=test-key python -m pytest tests/test_ai_validation.py -v`

预期：FAIL，因为 `app.services.ai_validation` 不存在。

- [ ] **步骤 3：实现校验器**

创建 `backend/app/services/ai_validation.py`：

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

- [ ] **步骤 4：新增 Prompt 构建器**

创建 `backend/app/services/ai_prompts.py`：

```python
ITEM_SYSTEM_PROMPT = (
    "你是今日看点的股票信息整理助手。你的任务是把输入内容整理成中性、可读、可追溯的信息摘要。"
    "你可以说明事件、影响解读、关注点和风险提示。"
    "你必须避免买入、卖出、持有等操作建议，避免价格预测和涨跌预测，避免"必然""确定""强烈推荐"等确定性表达。"
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

- [ ] **步骤 5：新增 OpenAI 兼容客户端**

创建 `backend/app/services/ai_client.py`：

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

- [ ] **步骤 6：运行校验测试**

执行：`cd backend && APP_SECRET_KEY=test-key python -m pytest tests/test_ai_validation.py -v`

预期：PASS。

- [ ] **步骤 7：提交**

```bash
git add backend/app/services/ai_client.py backend/app/services/ai_prompts.py backend/app/services/ai_validation.py backend/tests/test_ai_validation.py
git commit -m "feat(ai): add prompt client and output validation"
```

---

## 任务 4：新增候选筛选和单条加工 Service

**涉及文件：**
- 新增：`backend/app/services/ai_enrichment.py`
- 测试：`backend/tests/test_ai_enrichment.py`

- [ ] **步骤 1：编写候选筛选和加工测试**

创建 `backend/tests/test_ai_enrichment.py`：

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

- [ ] **步骤 2：运行测试，确认失败**

执行：`cd backend && APP_SECRET_KEY=test-key python -m pytest tests/test_ai_enrichment.py -v`

预期：FAIL，因为 `select_item_candidates` 尚未定义。

- [ ] **步骤 3：实现确定性候选筛选**

创建 `backend/app/services/ai_enrichment.py`，包含如下常量和函数：

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

- [ ] **步骤 4：新增单条加工 Service 骨架**

在 `backend/app/services/ai_enrichment.py` 中新增 `create_pending_enrichments(session, topic_id, raw_items)`，为筛出的候选条目创建 `AIItemEnrichment(status="pending")` 记录并返回。模型调用留待任务 5 实现。

- [ ] **步骤 5：运行测试**

执行：`cd backend && APP_SECRET_KEY=test-key python -m pytest tests/test_ai_enrichment.py -v`

预期：PASS。

- [ ] **步骤 6：提交**

```bash
git add backend/app/services/ai_enrichment.py backend/tests/test_ai_enrichment.py
git commit -m "feat(ai): add stock enrichment candidate selection"
```

---

## 任务 5：处理单条加工、同步看点并记录任务日志

**涉及文件：**
- 修改：`backend/app/services/ai_enrichment.py`
- 修改：`backend/app/services/jobs.py`
- 测试：`backend/tests/test_jobs_ai_integration.py`

- [ ] **步骤 1：编写集成测试**

创建 `backend/tests/test_jobs_ai_integration.py`，编写一个专注的 Service 级别测试：插入股票主题、来源、raw_item、默认 AI 模型配置和模拟 AI 返回。断言 `process_pending_item_enrichment(...)` 会创建 `AIItemEnrichment(status="generated")`、创建一条 `Highlight`、设置 `generated_by_model`，并创建 `AIGenerationJob(status="succeeded")`。

使用如下模拟返回：

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

- [ ] **步骤 2：运行测试，确认失败**

执行：`cd backend && APP_SECRET_KEY=test-key python -m pytest tests/test_jobs_ai_integration.py -v`

预期：FAIL，因为单条加工函数尚不存在。

- [ ] **步骤 3：实现处理函数**

在 `backend/app/services/ai_enrichment.py` 中新增：

- `process_item_enrichment(session, enrichment_id, post_json=None, trigger_type="crawl", retry_of_job_id=None)`
- `sync_highlight_from_enrichment(session, enrichment)`
- `retry_item_enrichment(session, job_id, post_json=None)`

必要行为：

- 调用模型前将加工状态设为 `"processing"`。
- 仅当 `trigger_type == "retry"` 时递增 `retry_count`。
- 调用模型前更新 `last_attempted_at`。
- `retry_count >= 3` 时拒绝重试。
- 使用 `get_default_ai_model(session)` 获取模型。
- 使用 `CryptoService` 解密 API Key。
- 调用 `AIClient.complete_json(...)`。
- 使用 `validate_item_enrichment_payload(...)` 校验输出。
- 保存生成字段。
- 设置 `status="generated"`、`generated_at`、`generated_by_model`。
- 为同一 `raw_item_id` 创建或更新一条 `Highlight`。
- 成功或失败时均创建 `AIGenerationJob`。

- [ ] **步骤 4：替换旧的内联看点生成路径**

修改 `backend/app/services/jobs.py`：

- 保留 `save_raw_items(...)`。
- 若 `source.enable_highlight` 为 true，调用 `create_pending_enrichments(session, source.topic_id, raw_items)`，然后对每条加工记录执行处理。
- 从 `run_crawl_job` 中移除 `_generate_highlights(...)` 的调用。
- 保持降级行为：AI 任务失败时不生成备用看点，原始内容仍可展示。

- [ ] **步骤 5：运行集成测试**

执行：`cd backend && APP_SECRET_KEY=test-key python -m pytest tests/test_jobs_ai_integration.py tests/test_ai_enrichment.py -v`

预期：PASS。

- [ ] **步骤 6：提交**

```bash
git add backend/app/services/ai_enrichment.py backend/app/services/jobs.py backend/tests/test_jobs_ai_integration.py
git commit -m "feat(ai): process item enrichments into highlights"
```

---

## 任务 6：新增主题汇总生成和公开 API

**涉及文件：**
- 修改：`backend/app/services/ai_enrichment.py`
- 修改：`backend/app/schemas/public.py`
- 修改：`backend/app/api/public.py`
- 修改：`backend/app/api/admin.py`
- 测试：`backend/tests/test_ai_public_api.py`

- [ ] **步骤 1：编写公开 API 测试**

创建 `backend/tests/test_ai_public_api.py`：

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

- [ ] **步骤 2：运行测试，确认失败**

执行：`cd backend && APP_SECRET_KEY=test-key python -m pytest tests/test_ai_public_api.py -v`

预期：FAIL，路由不存在或返回 404。

- [ ] **步骤 3：新增公开端 Schema**

在 `backend/app/schemas/public.py` 中新增 `AITopicSummaryItemRead` 和 `AITopicSummaryRead` DTO，包含字段：`title`、`reason`、`related`、`risk`、`source_refs`、`version`、`generated_at`。

- [ ] **步骤 4：新增公开端接口**

修改 `backend/app/api/public.py`：

- 导入 `AITopicSummary`。
- 按 slug 查询主题。
- 查询 `AITopicSummary`，条件：`topic_id`、`status == "generated"`，排序：`summary_date.desc(), version.desc()`。
- 无可用汇总时返回 404。

- [ ] **步骤 5：新增手动重新生成接口**

修改 `backend/app/api/admin.py`：

```python
@router.post("/ai/topic-summaries/stocks/regenerate")
def regenerate_stocks_ai_summary(session: Session = Depends(get_session)) -> dict:
    summary = generate_topic_summary(session, topic_slug="stocks", trigger_type="manual")
    session.commit()
    return {"id": summary.id, "version": summary.version, "status": summary.status}
```

在 `ai_enrichment.py` 中实现 `generate_topic_summary(...)`，使用最近 24 小时内已生成的加工结果和异动上下文，同日重新生成时递增 `version` 而非覆盖。

- [ ] **步骤 6：运行测试**

执行：`cd backend && APP_SECRET_KEY=test-key python -m pytest tests/test_ai_public_api.py -v`

预期：PASS。

- [ ] **步骤 7：提交**

```bash
git add backend/app/services/ai_enrichment.py backend/app/schemas/public.py backend/app/api/public.py backend/app/api/admin.py backend/tests/test_ai_public_api.py
git commit -m "feat(ai): add stock topic summary API"
```

---

## 任务 7：新增 AI 任务管理端 API 和重试接口

**涉及文件：**
- 修改：`backend/app/schemas/admin.py`
- 修改：`backend/app/api/admin.py`
- 测试：`backend/tests/test_ai_admin_api.py`

- [ ] **步骤 1：扩展管理端 API 测试**

在 `backend/tests/test_ai_admin_api.py` 中新增：

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

- [ ] **步骤 2：运行测试，确认失败**

执行：`cd backend && APP_SECRET_KEY=test-key python -m pytest tests/test_ai_admin_api.py -v`

预期：FAIL，`/api/admin/ai-jobs` 尚未实现。

- [ ] **步骤 3：新增管理端 Schema**

在 `backend/app/schemas/admin.py` 中新增 `AIJobRead` 和 `AIJobListResponse`。

- [ ] **步骤 4：新增接口**

修改 `backend/app/api/admin.py`：

- `GET /api/admin/ai-jobs?page=1&page_size=20`
- `POST /api/admin/ai-jobs/{job_id}/retry`

重试接口需调用 `retry_item_enrichment(...)`，任务不存在时返回 404，`retry_count >= 3` 时返回 400。

- [ ] **步骤 5：运行测试**

执行：`cd backend && APP_SECRET_KEY=test-key python -m pytest tests/test_ai_admin_api.py -v`

预期：PASS。

- [ ] **步骤 6：提交**

```bash
git add backend/app/schemas/admin.py backend/app/api/admin.py backend/tests/test_ai_admin_api.py
git commit -m "feat(ai): add generation job admin API"
```

---

## 任务 8：升级前端 API 类型和模型设置 UI

**涉及文件：**
- 修改：`frontend/src/api/types.ts`
- 修改：`frontend/src/api/client.ts`
- 修改：`frontend/src/pages/AdminSettingsPage.tsx`
- 测试：`frontend/src/__tests__/admin-ai-models.test.tsx`

- [ ] **步骤 1：编写失败的前端测试**

创建 `frontend/src/__tests__/admin-ai-models.test.tsx`，mock `fetchAIModels`、`createAIModel`、`updateAIModel`，并断言：

- 模型列表能渲染名称和 `has_api_key` 状态。
- 创建表单能提交 `name`、`base_url`、`model`、`api_key`、`is_default`、`enabled`、`notes`。
- 保存成功后 API Key 输入框清空。

- [ ] **步骤 2：运行测试，确认失败**

执行：`cd frontend && npm test -- admin-ai-models.test.tsx`

预期：FAIL，AI 模型 API 函数和模型列表 UI 不存在。

- [ ] **步骤 3：新增类型定义**

在 `frontend/src/api/types.ts` 中新增：

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

- [ ] **步骤 4：新增客户端函数**

在 `frontend/src/api/client.ts` 中新增：

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

- [ ] **步骤 5：升级 AdminSettingsPage**

将单模型表单替换为：

- 简洁的 AI 模型配置列表。
- 新增/编辑表单，字段来自 `AIModelConfigWrite`。
- API Key 占位符文字：`已配置，留空则不修改`。
- 显示 `默认`、`启用`、`API Key 已配置` 徽标。
- 非默认模型提供 `设为默认` 按钮。

- [ ] **步骤 6：运行前端测试**

执行：`cd frontend && npm test -- admin-ai-models.test.tsx`

预期：PASS。

- [ ] **步骤 7：提交**

```bash
git add frontend/src/api/types.ts frontend/src/api/client.ts frontend/src/pages/AdminSettingsPage.tsx frontend/src/__tests__/admin-ai-models.test.tsx
git commit -m "feat(ai): add model config settings UI"
```

---

## 任务 9：新增公开 AI 主题汇总 UI

**涉及文件：**
- 新增：`frontend/src/components/layout/AITopicSummary.tsx`
- 修改：`frontend/src/api/types.ts`
- 修改：`frontend/src/api/client.ts`
- 修改：`frontend/src/pages/TopicPage.tsx`
- 测试：`frontend/src/__tests__/ai-topic-summary.test.tsx`

- [ ] **步骤 1：编写失败的组件测试**

创建 `frontend/src/__tests__/ai-topic-summary.test.tsx`：

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

- [ ] **步骤 2：运行测试，确认失败**

执行：`cd frontend && npm test -- ai-topic-summary.test.tsx`

预期：FAIL，`AITopicSummary` 组件不存在。

- [ ] **步骤 3：新增公开端类型和 API**

在 `frontend/src/api/types.ts` 中新增 `AITopicSummaryResponse`，在 `frontend/src/api/client.ts` 中新增 `fetchAITopicSummary(slug: string)`。

- [ ] **步骤 4：实现组件**

创建 `frontend/src/components/layout/AITopicSummary.tsx`，包含：

- 带 `BrainCircuit` 图标的标题行。
- 3-5 条看点行。
- 涉及标的/板块标签片段。
- 风险提示文本。
- 生成时间。
- 固定免责声明：`AI 摘要，仅供信息参考`。
- `summary` 为 `null` 时不渲染。

- [ ] **步骤 5：仅在股票主题渲染**

修改 `frontend/src/pages/TopicPage.tsx`：

- 从 `/topics/{slug}` 中提取 `slug`。
- 若 `slug === "stocks"`，调用 `useQuery(["ai-topic-summary", slug], () => fetchAITopicSummary(slug))`。
- 404 或请求报错时不渲染任何内容。
- 加载中时在 `GridRenderer` 上方渲染简洁骨架屏。
- 有数据时在 `GridRenderer` 上方渲染 `AITopicSummary`。

- [ ] **步骤 6：运行测试**

执行：`cd frontend && npm test -- ai-topic-summary.test.tsx public-pages.test.tsx`

预期：PASS。

- [ ] **步骤 7：提交**

```bash
git add frontend/src/components/layout/AITopicSummary.tsx frontend/src/api/types.ts frontend/src/api/client.ts frontend/src/pages/TopicPage.tsx frontend/src/__tests__/ai-topic-summary.test.tsx
git commit -m "feat(ai): show stock topic AI summary"
```

---

## 任务 10：新增条目级 AI 增强展示

**涉及文件：**
- 修改：`frontend/src/components/layout/NewsTimeline.tsx`
- 修改：`frontend/src/components/layout/BlockCard.tsx`
- 修改：`frontend/src/components/layout/GridRenderer.tsx`
- 测试：`frontend/src/__tests__/public-pages.test.tsx`

- [ ] **步骤 1：编写失败的展示测试**

在 `frontend/src/__tests__/public-pages.test.tsx` 中新增断言，测试具有如下数据的时间轴/卡片条目：

```ts
ai_enrichment: {
  status: "generated",
  summary: "AI 生成的中性摘要。",
  tags: ["资金"],
  importance_score: 72,
}
```

能渲染 AI 摘要和标签；而 `status: "failed"` 或 `importance_score: 39` 的同一条目不渲染 AI 增强内容。

- [ ] **步骤 2：运行测试，确认失败**

执行：`cd frontend && npm test -- public-pages.test.tsx`

预期：FAIL，组件忽略了 `ai_enrichment` 字段。

- [ ] **步骤 3：新增条目类型和渲染门控**

在 `NewsTimeline.tsx` 和 `BlockCard.tsx` 中新增：

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

仅当 `shouldShowAI(...)` 为 true 时渲染 AI 摘要和标签，其他状态保持原始标题/正文可见。

- [ ] **步骤 4：从区块映射加工字段**

修改 `frontend/src/components/layout/GridRenderer.tsx`，当后端返回 `item.ai_enrichment` 时，将其传入 `BlockCard` 和 `NewsTimeline`。

- [ ] **步骤 5：运行测试**

执行：`cd frontend && npm test -- public-pages.test.tsx`

预期：PASS。

- [ ] **步骤 6：提交**

```bash
git add frontend/src/components/layout/NewsTimeline.tsx frontend/src/components/layout/BlockCard.tsx frontend/src/components/layout/GridRenderer.tsx frontend/src/__tests__/public-pages.test.tsx
git commit -m "feat(ai): show item-level enrichment on public blocks"
```

---

## 任务 11：新增 AI 任务管理页面

**涉及文件：**
- 新增：`frontend/src/pages/AdminAIJobsPage.tsx`
- 修改：`frontend/src/api/types.ts`
- 修改：`frontend/src/api/client.ts`
- 修改：`frontend/src/App.tsx`
- 修改：`frontend/src/components/admin/AdminSidebar.tsx`
- 测试：`frontend/src/__tests__/ai-jobs-page.test.tsx`

- [ ] **步骤 1：编写失败的管理页面测试**

创建 `frontend/src/__tests__/ai-jobs-page.test.tsx`，断言：

- 无任务时页面显示空状态。
- 失败任务渲染错误摘要和重试按钮。
- 点击重试按钮调用 `retryAIJob(job.id)`。

- [ ] **步骤 2：运行测试，确认失败**

执行：`cd frontend && npm test -- ai-jobs-page.test.tsx`

预期：FAIL，页面和 API 函数不存在。

- [ ] **步骤 3：新增类型定义和客户端函数**

在 `frontend/src/api/types.ts` 和 `frontend/src/api/client.ts` 中新增 `AIGenerationJob`、`AIJobListResponse`、`fetchAIJobs`、`retryAIJob`。

- [ ] **步骤 4：实现页面**

创建 `frontend/src/pages/AdminAIJobsPage.tsx`：

- 使用 `fetchAIJobs(1, 20)`。
- 展示任务类型、触发类型、状态、成功/失败数量、错误信息、开始/结束时间。
- 仅对 `status === "failed"` 的任务显示重试按钮。
- 重试成功后使 `["ai-jobs"]` 查询失效。

- [ ] **步骤 5：注册路由和导航**

修改 `frontend/src/App.tsx`：

```tsx
<Route path="/admin/ai-jobs" element={<AdminAIJobsPage />} />
```

修改 `frontend/src/components/admin/AdminSidebar.tsx`，新增带 `BrainCircuit` 或 `Sparkles` 图标的 AI 任务导航链接。

- [ ] **步骤 6：运行测试**

执行：`cd frontend && npm test -- ai-jobs-page.test.tsx admin-pages.test.tsx`

预期：PASS。

- [ ] **步骤 7：提交**

```bash
git add frontend/src/pages/AdminAIJobsPage.tsx frontend/src/api/types.ts frontend/src/api/client.ts frontend/src/App.tsx frontend/src/components/admin/AdminSidebar.tsx frontend/src/__tests__/ai-jobs-page.test.tsx
git commit -m "feat(ai): add generation jobs admin page"
```

---

## 任务 12：全面验证和浏览器 QA

**涉及文件：**
- 无新建源文件，除非验证过程发现缺陷。

- [ ] **步骤 1：运行后端测试**

执行：`cd backend && APP_SECRET_KEY=test-key python -m pytest tests/ -v`

预期：PASS。

- [ ] **步骤 2：运行前端测试**

执行：`cd frontend && npm test`

预期：PASS。

- [ ] **步骤 3：运行前端构建**

执行：`cd frontend && npm run build`

预期：PASS。若出现现有的 Vite 大文件 chunk 警告但无新的构建错误，可接受。

- [ ] **步骤 4：运行 diff 卫生检查**

执行：`git diff --check`

预期：无输出。

- [ ] **步骤 5：浏览器 QA**

使用项目现有命令启动前后端：

```bash
cd backend && APP_SECRET_KEY=test-key uvicorn app.main:app --reload
cd frontend && npm run dev
```

检验以下内容：

- `/admin/settings`：模型列表正常渲染，创建/编辑表单不暴露 API Key 明文。
- `/admin/ai-jobs`：空状态和失败任务状态正常渲染。
- `/topics/stocks`：无生成数据时 AI 汇总隐藏，原始区块仍正常展示。
- `/topics/stocks`：有种子/生成数据时，顶部 AI 模块出现在区块上方，不产生横向溢出。

- [ ] **步骤 6：最终提交或修复提交**

若浏览器 QA 需要修复，每项修复使用范围明确的提交信息，例如：

```bash
git add frontend/src/components/layout/AITopicSummary.tsx frontend/src/pages/TopicPage.tsx
git commit -m "fix(ai): correct stock summary empty state"
```

若无需修复，不创建空提交。

---

## 自检清单

- 规格覆盖：
  - 加密多模型配置：任务 1、2、8。
  - 单条加工（含重试字段和最大重试次数）：任务 1、5、7。
  - 主题汇总版本控制：任务 1、6。
  - 生成任务字段和重试日志：任务 1、5、7、11。
  - 候选筛选规则和阈值：任务 4。
  - Prompt 和输出校验：任务 3。
  - 公开顶部汇总和降级处理：任务 6、9。
  - 条目级展示规则：任务 10。
  - 完整测试和浏览器 QA：任务 12。

- 占位符检查：
  - 本计划使用了具体的文件名、命令、限制值和状态值。
  - 实施人员在每个任务完成后仍需检查当前导入情况，因为后续提交可能改变文件结构。

- 类型一致性：
  - 后端状态值：加工/汇总使用 `pending`、`processing`、`generated`、`failed`、`hidden`；任务使用 `pending`、`processing`、`succeeded`、`failed`、`partial`。
  - 前端 API 类型名称与后端资源名称对应：`AIModelConfig`、`AIGenerationJob`、`AITopicSummaryResponse`。
