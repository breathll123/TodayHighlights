# Block AI Prompt Template Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a conservative prompt-template architecture for block AI analysis: source types map to `news` / `rank` / `event`, and per-topic context plus extra forbidden rules are configurable from admin.

**Architecture:** Keep output specs, generic frameworks, forbidden base rules, and source-type mapping in code. Store only `topic_context` and `extra_forbidden` in `ai_prompt_templates`, keyed by `topic_slug + content_class`. At runtime, `analyze_block()` resolves topic slug and content class, loads an enabled template if present, builds the system prompt, and falls back to code defaults if no template exists.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, MySQL-compatible migrations, Pydantic, React, Vite, TanStack Query, Tailwind, Vitest.

---

## Scope Check

The spec is focused: it only changes block-level AI prompt assembly and admin management for prompt templates. It does not change existing item/topic summary prompts, auth, AI drawer behavior, token usage, or top market trends.

Current worktree note: there are pre-existing uncommitted edits in `backend/app/services/ai_prompts.py`, `frontend/src/__tests__/admin-pages.test.tsx`, and `frontend/src/__tests__/public-pages.test.tsx`. Do not overwrite or revert them. This plan touches some frontend tests later; if those files still contain user edits, merge new mock additions carefully.

## File Structure

### Backend

- Modify `backend/app/models/entities.py`
  - Add `AIPromptTemplate`.
- Create `backend/migrations/versions/20260607_0008_ai_prompt_templates.py`
  - Add `ai_prompt_templates`.
  - Seed conservative default templates for stocks, football, and ai.
- Create `backend/app/schemas/ai_prompt_template.py`
  - Read/write schemas for admin CRUD.
- Create `backend/app/services/ai_block_prompts.py`
  - `SOURCE_TYPE_TO_CLASS`
  - `get_content_class()`
  - `infer_topic_slug()`
  - `build_block_system_prompt()`
  - `get_enabled_prompt_template()`
- Modify `backend/app/services/ai_block_analysis.py`
  - Replace hardcoded `BLOCK_ANALYSIS_SYSTEM_PROMPT` call with runtime-built prompt.
- Modify `backend/app/api/admin.py`
  - Add prompt-template CRUD endpoints.
- Tests:
  - Modify `backend/tests/test_ai_block_analysis.py`
  - Create `backend/tests/test_ai_prompt_templates.py`

### Frontend

- Modify `frontend/src/api/types.ts`
  - Add prompt template types.
- Modify `frontend/src/api/client.ts`
  - Add prompt template admin API calls.
- Create `frontend/src/pages/AdminPromptTemplatesPage.tsx`
  - Table and lightweight form for `topic_slug`, `content_class`, `topic_context`, `extra_forbidden`, `enabled`, `notes`.
- Modify `frontend/src/components/admin/AdminSidebar.tsx`
  - Add “Prompt 模板” nav item.
- Modify `frontend/src/App.tsx`
  - Add `/admin/ai-prompts` route.
- Tests:
  - Create `frontend/src/__tests__/admin-prompt-templates.test.tsx`
  - Update existing admin test mocks only if required by route imports.

---

## Task 1: Backend Model And Migration

**Files:**
- Modify: `backend/app/models/entities.py`
- Create: `backend/migrations/versions/20260607_0008_ai_prompt_templates.py`
- Create: `backend/tests/test_ai_prompt_templates.py`

- [ ] **Step 1: Write failing table-shape test**

Create `backend/tests/test_ai_prompt_templates.py`:

```python
from sqlalchemy import inspect, select

from app.core.database import get_session
from app.models.entities import AIPromptTemplate


def test_ai_prompt_templates_table_columns_exist(client):
    session = next(client.app.dependency_overrides[get_session]())
    columns = {col["name"] for col in inspect(session.bind).get_columns("ai_prompt_templates")}

    assert {
        "id",
        "topic_slug",
        "content_class",
        "topic_context",
        "extra_forbidden",
        "enabled",
        "template_version",
        "updated_by_user_id",
        "notes",
        "created_at",
        "updated_at",
    }.issubset(columns)


def test_ai_prompt_template_model_can_store_context(client):
    session = next(client.app.dependency_overrides[get_session]())
    template = AIPromptTemplate(
        topic_slug="stocks",
        content_class="news",
        topic_context="关注政策信号",
        extra_forbidden="不得给出买卖建议",
        enabled=True,
        notes="test",
    )
    session.add(template)
    session.commit()

    saved = session.scalar(select(AIPromptTemplate).where(AIPromptTemplate.topic_slug == "stocks"))
    assert saved is not None
    assert saved.content_class == "news"
    assert saved.template_version == 1
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd backend
pytest tests/test_ai_prompt_templates.py::test_ai_prompt_templates_table_columns_exist tests/test_ai_prompt_templates.py::test_ai_prompt_template_model_can_store_context -q
```

Expected: fail because `AIPromptTemplate` and `ai_prompt_templates` do not exist.

- [ ] **Step 3: Add SQLAlchemy model**

In `backend/app/models/entities.py`, add this class after `AIModelConfig` or before `AIItemEnrichment`:

```python
class AIPromptTemplate(TimestampMixin, Base):
    __tablename__ = "ai_prompt_templates"
    __table_args__ = (
        UniqueConstraint("topic_slug", "content_class", name="uq_ai_prompt_template_topic_class"),
        Index("ix_ai_prompt_templates_enabled", "topic_slug", "content_class", "enabled"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_slug: Mapped[str] = mapped_column(String(80), nullable=False)
    content_class: Mapped[str] = mapped_column(String(30), nullable=False)
    topic_context: Mapped[str] = mapped_column(Text, default="", nullable=False)
    extra_forbidden: Mapped[str] = mapped_column(Text, default="", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    template_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
```

- [ ] **Step 4: Add Alembic migration**

Create `backend/migrations/versions/20260607_0008_ai_prompt_templates.py`:

```python
"""ai prompt templates

Revision ID: 20260607_0008
Revises: 20260606_0007
Create Date: 2026-06-07
"""

from alembic import op
import sqlalchemy as sa


revision = "20260607_0008"
down_revision = "20260606_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_prompt_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("topic_slug", sa.String(length=80), nullable=False),
        sa.Column("content_class", sa.String(length=30), nullable=False),
        sa.Column("topic_context", sa.Text(), nullable=False),
        sa.Column("extra_forbidden", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("template_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("topic_slug", "content_class", name="uq_ai_prompt_template_topic_class"),
    )
    op.create_index(
        "ix_ai_prompt_templates_enabled",
        "ai_prompt_templates",
        ["topic_slug", "content_class", "enabled"],
    )

    templates = [
        {
            "topic_slug": "stocks",
            "content_class": "news",
            "topic_context": "分析股票资讯时关注：政策信号、业绩变化、公告影响、板块联动和市场情绪。注意区分一次性事件和趋势性变化。",
            "extra_forbidden": "不得给出买入、卖出、持有、加仓、减仓等操作建议；不得给出价格预测、涨跌预测或收益承诺。",
            "notes": "默认股票资讯模板",
        },
        {
            "topic_slug": "stocks",
            "content_class": "rank",
            "topic_context": "分析股票榜单和行情时关注：资金集中度、板块联动、龙头效应、异常涨跌幅、成交或资金流变化。",
            "extra_forbidden": "不得给出买入、卖出、持有、加仓、减仓等操作建议；不得给出价格预测、涨跌预测或收益承诺。",
            "notes": "默认股票榜单模板",
        },
        {
            "topic_slug": "football",
            "content_class": "event",
            "topic_context": "分析足球赛事时关注：赛果、比赛状态、时间节点、积分影响、排名变化、主客场因素和后续赛程。",
            "extra_forbidden": "不得预测比分，不得把未开赛比赛描述为已发生事实。",
            "notes": "默认足球赛事模板",
        },
        {
            "topic_slug": "football",
            "content_class": "rank",
            "topic_context": "分析足球积分榜或排行榜时关注：排名变化、积分差距、净胜球、晋级或保级压力、赛程影响。",
            "extra_forbidden": "不得预测比分，不得把未开赛比赛描述为已发生事实。",
            "notes": "默认足球榜单模板",
        },
        {
            "topic_slug": "ai",
            "content_class": "news",
            "topic_context": "分析 AI 资讯时关注：模型能力变化、产品发布、商业化进展、开源与闭源格局、监管动态和产业影响。",
            "extra_forbidden": "",
            "notes": "默认 AI 资讯模板",
        },
    ]
    op.bulk_insert(sa.table(
        "ai_prompt_templates",
        sa.column("topic_slug", sa.String),
        sa.column("content_class", sa.String),
        sa.column("topic_context", sa.Text),
        sa.column("extra_forbidden", sa.Text),
        sa.column("enabled", sa.Boolean),
        sa.column("template_version", sa.Integer),
        sa.column("notes", sa.Text),
    ), [{**row, "enabled": True, "template_version": 1} for row in templates])


def downgrade() -> None:
    op.drop_index("ix_ai_prompt_templates_enabled", table_name="ai_prompt_templates")
    op.drop_table("ai_prompt_templates")
```

Important MySQL constraint: do not use `server_default` for `Text` columns.

- [ ] **Step 5: Run model tests**

Run:

```bash
cd backend
pytest tests/test_ai_prompt_templates.py::test_ai_prompt_templates_table_columns_exist tests/test_ai_prompt_templates.py::test_ai_prompt_template_model_can_store_context -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/entities.py backend/migrations/versions/20260607_0008_ai_prompt_templates.py backend/tests/test_ai_prompt_templates.py
git commit -m "feat(ai): add prompt template model"
```

---

## Task 2: Prompt Assembly Service

**Files:**
- Create: `backend/app/services/ai_block_prompts.py`
- Modify: `backend/tests/test_ai_prompt_templates.py`

- [ ] **Step 1: Add failing prompt-service tests**

Append to `backend/tests/test_ai_prompt_templates.py`:

```python
from app.services.ai_block_prompts import (
    build_block_system_prompt,
    get_content_class,
    infer_topic_slug,
)


def test_get_content_class_maps_existing_source_types():
    assert get_content_class("aihot_news") == "news"
    assert get_content_class("eastmoney_capital_flow") == "rank"
    assert get_content_class("qiumiwu_schedule") == "event"
    assert get_content_class("unknown_source") == "news"


def test_infer_topic_slug_from_routes():
    assert infer_topic_slug("/topics/stocks") == "stocks"
    assert infer_topic_slug("/topics/football") == "football"
    assert infer_topic_slug("/topics/ai") == "ai"
    assert infer_topic_slug("/") == "summary"


def test_build_block_system_prompt_injects_template_context():
    template = AIPromptTemplate(
        topic_slug="ai",
        content_class="news",
        topic_context="关注模型能力变化",
        extra_forbidden="不得编造机构名称",
        enabled=True,
    )

    prompt = build_block_system_prompt("ai", "news", template)

    assert "当前分析领域：ai" in prompt
    assert "【领域背景】" in prompt
    assert "关注模型能力变化" in prompt
    assert "不得编造机构名称" in prompt
    assert "summary_points" in prompt
    assert "只输出合法 JSON" in prompt


def test_build_block_system_prompt_without_template_uses_default_framework():
    prompt = build_block_system_prompt("football", "event", None)

    assert "当前分析领域：football" in prompt
    assert "提取关键事实、时间、状态和结果" in prompt
    assert "【领域背景】" not in prompt
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd backend
pytest tests/test_ai_prompt_templates.py::test_get_content_class_maps_existing_source_types tests/test_ai_prompt_templates.py::test_infer_topic_slug_from_routes tests/test_ai_prompt_templates.py::test_build_block_system_prompt_injects_template_context tests/test_ai_prompt_templates.py::test_build_block_system_prompt_without_template_uses_default_framework -q
```

Expected: fail because `app.services.ai_block_prompts` does not exist.

- [ ] **Step 3: Add prompt assembly service**

Create `backend/app/services/ai_block_prompts.py`:

```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import AIPromptTemplate

SOURCE_TYPE_TO_CLASS: dict[str, str] = {
    "tonghuashun_news": "news",
    "eastmoney_announcements": "news",
    "aihot_news": "news",
    "hot_stocks": "rank",
    "hot_events": "rank",
    "xueqiu_hot_cn": "rank",
    "xueqiu_hot_hk": "rank",
    "xueqiu_hot_us": "rank",
    "screener": "rank",
    "eastmoney_sectors": "rank",
    "eastmoney_industry": "rank",
    "eastmoney_indices": "rank",
    "eastmoney_capital_flow": "rank",
    "eastmoney_longhu": "rank",
    "qiumiwu_standings": "rank",
    "datalearner_leaderboard": "rank",
    "datalearner_aa_index": "rank",
    "qiumiwu_matches": "event",
    "qiumiwu_fixtures": "event",
    "qiumiwu_schedule": "event",
}

_FRAMEWORK_NEWS = (
    "【分析流程】\n"
    "1. 识别增量信息，排除重复和常规内容。\n"
    "2. 判断事件可能影响的对象、范围和路径。\n"
    "3. 将多个相关内容合并成更高层级看点。\n"
    "4. 指出信息不足、来源单一或前提不明确的地方。\n"
)

_FRAMEWORK_RANK = (
    "【分析流程】\n"
    "1. 识别数值、排名、资金、涨跌幅、积分等异常项。\n"
    "2. 判断异动是分散还是集中，集中在哪些方向。\n"
    "3. 总结当前结构反映的偏好、压力或变化。\n"
    "4. 指出延续或反转需要观察的后续信号。\n"
)

_FRAMEWORK_EVENT = (
    "【分析流程】\n"
    "1. 提取关键事实、时间、状态和结果。\n"
    "2. 判断事件对后续节奏、排名、赛程或相关主体的影响。\n"
    "3. 识别超预期、异常或值得关注的变化。\n"
    "4. 说明下一步值得关注的关键节点。\n"
)

_FRAMEWORKS = {
    "news": _FRAMEWORK_NEWS,
    "rank": _FRAMEWORK_RANK,
    "event": _FRAMEWORK_EVENT,
}

_OUTPUT_SPEC = (
    "【输出字段】\n"
    "- summary_points: 字符串数组，1-4 条，每条不超过 160 字。\n"
    "- key_changes: 字符串数组，0-3 条，每条不超过 140 字。\n"
    "- risk_points: 字符串数组，0-2 条，每条不超过 140 字。\n"
    "- related_entities: 字符串数组，0-8 个，每个不超过 40 字。\n"
    "- confidence: 0 到 1 的数字。\n"
)

_FORBIDDEN_BASE = (
    "【禁止】\n"
    "- 不得把输入标题直接复制成 summary_points。\n"
    "- 不得使用「值得关注」「持续观察」「市场活跃」等无信息量套话收尾。\n"
    "- 只能基于提供内容分析，不得补充外部事实。\n"
    "- 不得编造来源、数据、比分、公司、股票或事件。\n"
    "- 只输出合法 JSON，不输出 Markdown，不输出代码块，不输出额外解释。\n"
)


def get_content_class(source_type: str) -> str:
    return SOURCE_TYPE_TO_CLASS.get(source_type, "news")


def infer_topic_slug(page_route: str) -> str:
    parts = [part for part in page_route.strip("/").split("/") if part]
    if len(parts) >= 2 and parts[0] == "topics":
        return parts[1]
    return "summary"


def get_enabled_prompt_template(session: Session, topic_slug: str, content_class: str) -> AIPromptTemplate | None:
    return session.scalar(
        select(AIPromptTemplate)
        .where(
            AIPromptTemplate.topic_slug == topic_slug,
            AIPromptTemplate.content_class == content_class,
            AIPromptTemplate.enabled.is_(True),
        )
        .limit(1)
    )


def build_block_system_prompt(
    topic_slug: str,
    content_class: str,
    template: AIPromptTemplate | None,
) -> str:
    framework = _FRAMEWORKS.get(content_class, _FRAMEWORK_NEWS)
    sections = [
        f"你是 DataFlow 的内容分析助手，当前分析领域：{topic_slug}。",
    ]
    if template is not None and template.topic_context.strip():
        sections.append(f"【领域背景】\n{template.topic_context.strip()}")
    sections.extend([framework.strip(), _OUTPUT_SPEC.strip(), _FORBIDDEN_BASE.strip()])
    if template is not None and template.extra_forbidden.strip():
        sections.append(f"【额外禁止】\n{template.extra_forbidden.strip()}")
    return "\n\n".join(sections)
```

- [ ] **Step 4: Run prompt service tests**

Run:

```bash
cd backend
pytest tests/test_ai_prompt_templates.py -q
```

Expected: all prompt template tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai_block_prompts.py backend/tests/test_ai_prompt_templates.py
git commit -m "feat(ai): add block prompt assembly"
```

---

## Task 3: Connect Prompt Templates To Block Analysis

**Files:**
- Modify: `backend/app/services/ai_block_analysis.py`
- Modify: `backend/tests/test_ai_block_analysis.py`

- [ ] **Step 1: Add failing integration test**

Append to `backend/tests/test_ai_block_analysis.py`:

```python
from app.models.entities import AIPromptTemplate


def test_analyze_block_uses_topic_prompt_template(client):
    session = next(client.app.dependency_overrides[get_session]())
    user, block = _seed_user_model_block(session)
    block.page_route = "/topics/stocks"
    block.source_type = "eastmoney_capital_flow"
    session.add(
        AIPromptTemplate(
            topic_slug="stocks",
            content_class="rank",
            topic_context="关注资金集中度",
            extra_forbidden="不得建议加仓",
            enabled=True,
        )
    )
    session.commit()
    captured: dict = {}

    async def fake_post(payload):
        captured["system"] = payload["messages"][0]["content"]
        return {
            "choices": [{"message": {"content": "{\"summary_points\":[\"资金集中在少数方向\"],\"key_changes\":[],\"risk_points\":[],\"related_entities\":[],\"confidence\":0.8}"}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
        }

    analysis = analyze_block(
        session,
        user=user,
        page_route="/topics/stocks",
        block_id=block.id,
        post_json=fake_post,
        resolved_data=[{"id": 1, "title": "资金流", "summary": "主力资金净流入", "score": 88}],
    )

    assert analysis.status == "generated"
    assert "关注资金集中度" in captured["system"]
    assert "不得建议加仓" in captured["system"]
    assert "识别数值、排名、资金、涨跌幅、积分等异常项" in captured["system"]
```

- [ ] **Step 2: Run integration test to verify failure**

Run:

```bash
cd backend
pytest tests/test_ai_block_analysis.py::test_analyze_block_uses_topic_prompt_template -q
```

Expected: fail because `analyze_block()` still uses the hardcoded `BLOCK_ANALYSIS_SYSTEM_PROMPT`.

- [ ] **Step 3: Update block analysis service imports**

In `backend/app/services/ai_block_analysis.py`, remove the hardcoded `BLOCK_ANALYSIS_SYSTEM_PROMPT` constant and import:

```python
from app.services.ai_block_prompts import (
    build_block_system_prompt,
    get_content_class,
    get_enabled_prompt_template,
    infer_topic_slug,
)
```

Keep `BLOCK_ANALYSIS_TTL_MINUTES`, `MAX_ANALYSIS_ITEMS`, and `MAX_ITEM_SUMMARY_CHARS`.

- [ ] **Step 4: Build runtime system prompt in analyze_block**

In `analyze_block()`, replace:

```python
prompt = block_user_prompt(block, data)
result = asyncio.run(client.complete_json_with_usage(BLOCK_ANALYSIS_SYSTEM_PROMPT, prompt))
```

with:

```python
topic_slug = infer_topic_slug(page_route)
content_class = get_content_class(block.source_type)
template = get_enabled_prompt_template(session, topic_slug, content_class)
system_prompt = build_block_system_prompt(topic_slug, content_class, template)
prompt = block_user_prompt(block, data)
result = asyncio.run(client.complete_json_with_usage(system_prompt, prompt))
```

- [ ] **Step 5: Run block analysis tests**

Run:

```bash
cd backend
pytest tests/test_ai_block_analysis.py tests/test_ai_prompt_templates.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/ai_block_analysis.py backend/tests/test_ai_block_analysis.py
git commit -m "feat(ai): use prompt templates for block analysis"
```

---

## Task 4: Admin Prompt Template API

**Files:**
- Create: `backend/app/schemas/ai_prompt_template.py`
- Modify: `backend/app/api/admin.py`
- Modify: `backend/tests/test_ai_prompt_templates.py`

- [ ] **Step 1: Add failing admin API tests**

Append to `backend/tests/test_ai_prompt_templates.py`:

```python
from app.services.auth_service import create_token
from app.models.entities import User


def _admin_headers(session):
    admin = User(username="template-admin", email=None, password_hash="hash", role="admin", status="active")
    session.add(admin)
    session.commit()
    return {"Authorization": f"Bearer {create_token(admin)}"}


def test_admin_prompt_template_crud(client):
    session = next(client.app.dependency_overrides[get_session]())
    headers = _admin_headers(session)

    created = client.post(
        "/api/admin/ai-prompt-templates",
        json={
            "topic_slug": "crypto",
            "content_class": "rank",
            "topic_context": "关注 BTC 主导率",
            "extra_forbidden": "不得承诺收益",
            "enabled": True,
            "notes": "crypto rank",
        },
        headers=headers,
    )
    assert created.status_code == 200
    template_id = created.json()["id"]
    assert created.json()["template_version"] == 1

    listed = client.get("/api/admin/ai-prompt-templates", headers=headers)
    assert listed.status_code == 200
    assert any(item["topic_slug"] == "crypto" for item in listed.json())

    updated = client.put(
        f"/api/admin/ai-prompt-templates/{template_id}",
        json={
            "topic_slug": "crypto",
            "content_class": "rank",
            "topic_context": "关注 BTC 主导率和链上数据",
            "extra_forbidden": "不得承诺收益",
            "enabled": False,
            "notes": "updated",
        },
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["enabled"] is False
    assert updated.json()["template_version"] == 2

    deleted = client.delete(f"/api/admin/ai-prompt-templates/{template_id}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": True}
```

- [ ] **Step 2: Run API test to verify failure**

Run:

```bash
cd backend
pytest tests/test_ai_prompt_templates.py::test_admin_prompt_template_crud -q
```

Expected: fail because admin prompt template endpoints do not exist.

- [ ] **Step 3: Add schemas**

Create `backend/app/schemas/ai_prompt_template.py`:

```python
from datetime import datetime

from pydantic import BaseModel, Field


class AIPromptTemplateWrite(BaseModel):
    topic_slug: str = Field(min_length=1, max_length=80)
    content_class: str = Field(pattern="^(news|rank|event)$")
    topic_context: str = Field(default="", max_length=4000)
    extra_forbidden: str = Field(default="", max_length=2000)
    enabled: bool = True
    notes: str = Field(default="", max_length=1000)


class AIPromptTemplateRead(BaseModel):
    id: int
    topic_slug: str
    content_class: str
    topic_context: str
    extra_forbidden: str
    enabled: bool
    template_version: int
    updated_by_user_id: int | None
    notes: str
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 4: Add admin endpoints**

In `backend/app/api/admin.py`, import:

```python
from app.models.entities import AIPromptTemplate
from app.schemas.ai_prompt_template import AIPromptTemplateRead, AIPromptTemplateWrite
```

Add these endpoints near other AI admin endpoints:

```python
def _serialize_prompt_template(template: AIPromptTemplate) -> AIPromptTemplateRead:
    return AIPromptTemplateRead(
        id=template.id,
        topic_slug=template.topic_slug,
        content_class=template.content_class,
        topic_context=template.topic_context,
        extra_forbidden=template.extra_forbidden,
        enabled=template.enabled,
        template_version=template.template_version,
        updated_by_user_id=template.updated_by_user_id,
        notes=template.notes,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


@router.get("/ai-prompt-templates", response_model=list[AIPromptTemplateRead])
def list_prompt_templates(session: Session = Depends(get_session)) -> list[AIPromptTemplateRead]:
    templates = session.scalars(
        select(AIPromptTemplate).order_by(AIPromptTemplate.topic_slug, AIPromptTemplate.content_class)
    ).all()
    return [_serialize_prompt_template(template) for template in templates]


@router.post("/ai-prompt-templates", response_model=AIPromptTemplateRead)
def create_prompt_template(
    payload: AIPromptTemplateWrite,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> AIPromptTemplateRead:
    template = AIPromptTemplate(
        topic_slug=payload.topic_slug.strip(),
        content_class=payload.content_class,
        topic_context=payload.topic_context.strip(),
        extra_forbidden=payload.extra_forbidden.strip(),
        enabled=payload.enabled,
        updated_by_user_id=user.id,
        notes=payload.notes.strip(),
    )
    session.add(template)
    session.commit()
    session.refresh(template)
    return _serialize_prompt_template(template)


@router.put("/ai-prompt-templates/{template_id}", response_model=AIPromptTemplateRead)
def update_prompt_template(
    template_id: int,
    payload: AIPromptTemplateWrite,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> AIPromptTemplateRead:
    template = session.get(AIPromptTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Prompt template not found")
    template.topic_slug = payload.topic_slug.strip()
    template.content_class = payload.content_class
    template.topic_context = payload.topic_context.strip()
    template.extra_forbidden = payload.extra_forbidden.strip()
    template.enabled = payload.enabled
    template.notes = payload.notes.strip()
    template.updated_by_user_id = user.id
    template.template_version += 1
    session.commit()
    session.refresh(template)
    return _serialize_prompt_template(template)


@router.delete("/ai-prompt-templates/{template_id}")
def delete_prompt_template(template_id: int, session: Session = Depends(get_session)) -> dict:
    template = session.get(AIPromptTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Prompt template not found")
    session.delete(template)
    session.commit()
    return {"deleted": True}
```

- [ ] **Step 5: Run backend prompt-template tests**

Run:

```bash
cd backend
pytest tests/test_ai_prompt_templates.py tests/test_ai_block_analysis.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/admin.py backend/app/schemas/ai_prompt_template.py backend/tests/test_ai_prompt_templates.py
git commit -m "feat(admin): manage ai prompt templates"
```

---

## Task 5: Frontend Prompt Template Management

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/client.ts`
- Create: `frontend/src/pages/AdminPromptTemplatesPage.tsx`
- Modify: `frontend/src/components/admin/AdminSidebar.tsx`
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/__tests__/admin-prompt-templates.test.tsx`
- Modify only if necessary: `frontend/src/__tests__/admin-pages.test.tsx`

- [ ] **Step 1: Add failing frontend test**

Create `frontend/src/__tests__/admin-prompt-templates.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { AdminPromptTemplatesPage } from "@/pages/AdminPromptTemplatesPage";

vi.mock("@/api/client", () => ({
  fetchAIPromptTemplates: vi.fn().mockResolvedValue([
    {
      id: 1,
      topic_slug: "stocks",
      content_class: "news",
      topic_context: "关注政策信号",
      extra_forbidden: "不得给出买卖建议",
      enabled: true,
      template_version: 1,
      updated_by_user_id: 1,
      notes: "默认",
      created_at: "2026-06-07T00:00:00",
      updated_at: "2026-06-07T00:00:00",
    },
  ]),
  createAIPromptTemplate: vi.fn(),
  updateAIPromptTemplate: vi.fn(),
  deleteAIPromptTemplate: vi.fn(),
}));

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe("AdminPromptTemplatesPage", () => {
  it("renders prompt templates and constrained form fields", async () => {
    render(<AdminPromptTemplatesPage />, { wrapper: Wrapper });

    expect(await screen.findByText("Prompt 模板")).toBeInTheDocument();
    expect(screen.getByText("stocks")).toBeInTheDocument();
    expect(screen.getByText("news")).toBeInTheDocument();
    expect(screen.getByLabelText("主题 slug")).toBeInTheDocument();
    expect(screen.getByLabelText("内容类型")).toBeInTheDocument();
    expect(screen.getByLabelText("领域背景")).toBeInTheDocument();
    expect(screen.getByLabelText("额外禁令")).toBeInTheDocument();
    expect(screen.queryByLabelText("override_framework")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run frontend test to verify failure**

Run:

```bash
cd frontend
npm test -- src/__tests__/admin-prompt-templates.test.tsx
```

Expected: fail because `AdminPromptTemplatesPage` does not exist.

- [ ] **Step 3: Add frontend types and API calls**

In `frontend/src/api/types.ts`, add:

```ts
export interface AIPromptTemplate {
  id: number;
  topic_slug: string;
  content_class: "news" | "rank" | "event";
  topic_context: string;
  extra_forbidden: string;
  enabled: boolean;
  template_version: number;
  updated_by_user_id: number | null;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface AIPromptTemplateWrite {
  topic_slug: string;
  content_class: "news" | "rank" | "event";
  topic_context: string;
  extra_forbidden: string;
  enabled: boolean;
  notes: string;
}
```

In `frontend/src/api/client.ts`, import these types and add:

```ts
export function fetchAIPromptTemplates(): Promise<AIPromptTemplate[]> {
  return api.get<AIPromptTemplate[]>("/api/admin/ai-prompt-templates").then((r) => r.data);
}

export function createAIPromptTemplate(data: AIPromptTemplateWrite): Promise<AIPromptTemplate> {
  return api.post<AIPromptTemplate>("/api/admin/ai-prompt-templates", data).then((r) => r.data);
}

export function updateAIPromptTemplate(id: number, data: AIPromptTemplateWrite): Promise<AIPromptTemplate> {
  return api.put<AIPromptTemplate>(`/api/admin/ai-prompt-templates/${id}`, data).then((r) => r.data);
}

export function deleteAIPromptTemplate(id: number): Promise<{ deleted: boolean }> {
  return api.delete(`/api/admin/ai-prompt-templates/${id}`).then((r) => r.data);
}
```

- [ ] **Step 4: Add admin page**

Create `frontend/src/pages/AdminPromptTemplatesPage.tsx`:

```tsx
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { createAIPromptTemplate, deleteAIPromptTemplate, fetchAIPromptTemplates, updateAIPromptTemplate } from "@/api/client";
import type { AIPromptTemplate, AIPromptTemplateWrite } from "@/api/types";
import { AdminPageHeader } from "@/components/admin/AdminPageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";

const emptyForm: AIPromptTemplateWrite = {
  topic_slug: "stocks",
  content_class: "news",
  topic_context: "",
  extra_forbidden: "",
  enabled: true,
  notes: "",
};

export function AdminPromptTemplatesPage() {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<AIPromptTemplate | null>(null);
  const [form, setForm] = useState<AIPromptTemplateWrite>(emptyForm);
  const { data: templates = [], isLoading } = useQuery({ queryKey: ["ai-prompt-templates"], queryFn: fetchAIPromptTemplates });
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["ai-prompt-templates"] });

  const createMutation = useMutation({ mutationFn: createAIPromptTemplate, onSuccess: invalidate });
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: AIPromptTemplateWrite }) => updateAIPromptTemplate(id, data),
    onSuccess: invalidate,
  });
  const deleteMutation = useMutation({ mutationFn: deleteAIPromptTemplate, onSuccess: invalidate });

  const submit = () => {
    if (editing) {
      updateMutation.mutate({ id: editing.id, data: form });
    } else {
      createMutation.mutate(form);
    }
    setEditing(null);
    setForm(emptyForm);
  };

  return (
    <div className="space-y-5">
      <AdminPageHeader eyebrow="Prompt Templates" title="Prompt 模板" description="按主题和内容类型维护区块 AI 分析的领域背景与额外禁令。" />

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="overflow-hidden rounded-lg border bg-card">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-muted-foreground">
              <tr>
                <th className="px-4 py-3 text-left">主题</th>
                <th className="px-4 py-3 text-left">类型</th>
                <th className="px-4 py-3 text-left">版本</th>
                <th className="px-4 py-3 text-left">状态</th>
                <th className="px-4 py-3 text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr><td className="px-4 py-4" colSpan={5}>加载中</td></tr>
              ) : templates.map((template) => (
                <tr key={template.id} className="border-t">
                  <td className="px-4 py-3">{template.topic_slug}</td>
                  <td className="px-4 py-3">{template.content_class}</td>
                  <td className="px-4 py-3">v{template.template_version}</td>
                  <td className="px-4 py-3">{template.enabled ? "启用" : "停用"}</td>
                  <td className="space-x-2 px-4 py-3 text-right">
                    <Button size="sm" variant="outline" onClick={() => { setEditing(template); setForm({
                      topic_slug: template.topic_slug,
                      content_class: template.content_class,
                      topic_context: template.topic_context,
                      extra_forbidden: template.extra_forbidden,
                      enabled: template.enabled,
                      notes: template.notes,
                    }); }}>编辑</Button>
                    <Button size="sm" variant="outline" onClick={() => deleteMutation.mutate(template.id)}>删除</Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="space-y-4 rounded-lg border bg-card p-4">
          <div className="space-y-2">
            <Label htmlFor="topic_slug">主题 slug</Label>
            <Input id="topic_slug" value={form.topic_slug} onChange={(event) => setForm({ ...form, topic_slug: event.target.value })} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="content_class">内容类型</Label>
            <Select value={form.content_class} onValueChange={(value: "news" | "rank" | "event") => setForm({ ...form, content_class: value })}>
              <SelectTrigger id="content_class"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="news">news</SelectItem>
                <SelectItem value="rank">rank</SelectItem>
                <SelectItem value="event">event</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="topic_context">领域背景</Label>
            <textarea id="topic_context" className="min-h-28 w-full rounded-md border bg-background px-3 py-2 text-sm" value={form.topic_context} onChange={(event) => setForm({ ...form, topic_context: event.target.value })} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="extra_forbidden">额外禁令</Label>
            <textarea id="extra_forbidden" className="min-h-24 w-full rounded-md border bg-background px-3 py-2 text-sm" value={form.extra_forbidden} onChange={(event) => setForm({ ...form, extra_forbidden: event.target.value })} />
          </div>
          <div className="flex items-center justify-between">
            <Label htmlFor="enabled">启用</Label>
            <Switch id="enabled" checked={form.enabled} onCheckedChange={(checked) => setForm({ ...form, enabled: checked })} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="notes">备注</Label>
            <Input id="notes" value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} />
          </div>
          <Button className="w-full" onClick={submit}>{editing ? "保存模板" : "新增模板"}</Button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Add route and sidebar item**

In `frontend/src/App.tsx`, import:

```tsx
import { AdminPromptTemplatesPage } from "./pages/AdminPromptTemplatesPage";
```

Add route:

```tsx
<Route path="/admin/ai-prompts" element={<AdminPromptTemplatesPage />} />
```

In `frontend/src/components/admin/AdminSidebar.tsx`, add `ScrollText` to the lucide import and add:

```tsx
{ href: "/admin/ai-prompts", label: "Prompt 模板", icon: ScrollText },
```

Place it near `AI 任务` and `AI 用量`.

- [ ] **Step 6: Update existing test mocks if imports require it**

If `frontend/src/__tests__/admin-pages.test.tsx` or `frontend/src/__tests__/public-pages.test.tsx` fail because `client.ts` now exports new functions, add these mocked functions to their existing `vi.mock("../api/client", ...)` blocks:

```ts
fetchAIPromptTemplates: vi.fn().mockResolvedValue([]),
createAIPromptTemplate: vi.fn(),
updateAIPromptTemplate: vi.fn(),
deleteAIPromptTemplate: vi.fn(),
```

Preserve any existing user edits in those files.

- [ ] **Step 7: Run frontend prompt-template test**

Run:

```bash
cd frontend
npm test -- src/__tests__/admin-prompt-templates.test.tsx
```

Expected: pass.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/api/types.ts frontend/src/api/client.ts frontend/src/pages/AdminPromptTemplatesPage.tsx frontend/src/components/admin/AdminSidebar.tsx frontend/src/App.tsx frontend/src/__tests__/admin-prompt-templates.test.tsx frontend/src/__tests__/admin-pages.test.tsx frontend/src/__tests__/public-pages.test.tsx
git commit -m "feat(admin): add prompt template management"
```

Before committing, check `git diff --cached --name-only` and ensure any staged changes in `admin-pages.test.tsx` or `public-pages.test.tsx` are only mock additions required by this task.

---

## Task 6: Full Verification

**Files:**
- Modify only files from Tasks 1-5 if verification reveals a concrete defect.

- [ ] **Step 1: Run backend targeted tests**

Run:

```bash
cd backend
pytest tests/test_ai_prompt_templates.py tests/test_ai_block_analysis.py tests/test_admin_users_usage.py tests/test_auth_api.py -q
```

Expected: pass.

- [ ] **Step 2: Run backend suite excluding known external network test if needed**

Run:

```bash
cd backend
pytest -q -k "not test_gainers"
```

Expected: pass. If `test_gainers` is run separately, it may fail due external Eastmoney DNS and should be reported as external-network residual risk.

- [ ] **Step 3: Run frontend tests**

Run:

```bash
cd frontend
npm test -- --run
```

Expected: pass.

- [ ] **Step 4: Run frontend build**

Run:

```bash
cd frontend
npm run build
```

Expected: Vite build succeeds. Existing large chunk warnings are acceptable if unchanged.

- [ ] **Step 5: Run migration check**

Run:

```bash
cd backend
python -m alembic upgrade head
```

Expected: migration applies to head without MySQL TEXT or JSON default errors.

- [ ] **Step 6: Manual behavior check**

Start the app using the existing local workflow:

```bash
cd backend
/Users/lws/opt/anaconda3/envs/daily_highlights/bin/uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5175
```

Verify:

- `/admin/ai-prompts` lists default templates.
- Editing `ai + news` changes `topic_context`.
- Generating an AI page block analysis uses the updated context.
- Disabling the template falls back to the default code framework.
- The page does not expose `override_framework`.

- [ ] **Step 7: Run diff check**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors. Status may still show unrelated pre-existing user edits if they were not part of this implementation; do not revert them.

- [ ] **Step 8: Commit verification fixes if needed**

If Task 6 required code changes, commit only the changed implementation files:

```bash
git status --short
git add backend/app/models/entities.py backend/migrations/versions/20260607_0008_ai_prompt_templates.py backend/app/services/ai_block_prompts.py backend/app/services/ai_block_analysis.py backend/app/api/admin.py backend/app/schemas/ai_prompt_template.py backend/tests/test_ai_prompt_templates.py backend/tests/test_ai_block_analysis.py frontend/src/api/types.ts frontend/src/api/client.ts frontend/src/pages/AdminPromptTemplatesPage.tsx frontend/src/components/admin/AdminSidebar.tsx frontend/src/App.tsx frontend/src/__tests__/admin-prompt-templates.test.tsx
git commit -m "fix(ai): polish prompt template flow"
```

If verification required no code changes, do not create an empty commit.

