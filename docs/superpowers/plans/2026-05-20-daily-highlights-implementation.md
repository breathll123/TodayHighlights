# 今日看点 MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working thin full-stack MVP for a Xueqiu-based stock daily highlights system with manual Cookie configuration, crawl jobs, AI summaries, MySQL persistence, React public pages, and React admin pages.

**Architecture:** Use a modular monolith: one FastAPI backend owns APIs, database access, Xueqiu adapter, scheduler, and summarizer interfaces; one Vite React app owns public reading and admin workflows. Keep crawler, summarizer, content, and admin modules separated so later websites can be added as new adapters.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2, Alembic, PyMySQL, Pydantic Settings, APScheduler, httpx, cryptography/Fernet, pytest; Vite, React, TypeScript, React Router, TanStack Query, Vitest, Testing Library.

---

## File Structure

Create this structure:

```text
backend/
  alembic.ini
  environment.yml
  pyproject.toml
  app/
    __init__.py
    main.py
    api/
      __init__.py
      public.py
      admin.py
    core/
      __init__.py
      config.py
      crypto.py
      database.py
      scheduler.py
    models/
      __init__.py
      entities.py
    schemas/
      __init__.py
      admin.py
      public.py
    services/
      __init__.py
      content.py
      jobs.py
      settings.py
      summarizer.py
    sources/
      __init__.py
      base.py
      xueqiu.py
  migrations/
    env.py
    script.py.mako
    versions/
      20260520_0001_initial.py
  tests/
    fixtures/
      xueqiu_timeline.json
    test_crypto.py
    test_models.py
    test_xueqiu_adapter.py
    test_content_service.py
    test_summarizer.py
    test_admin_api.py
    test_public_api.py
frontend/
  index.html
  package.json
  tsconfig.json
  vite.config.ts
  src/
    main.tsx
    api/client.ts
    api/types.ts
    App.tsx
    pages/
      SummaryPage.tsx
      StockTopicPage.tsx
      AdminSourcesPage.tsx
      AdminJobsPage.tsx
      AdminHighlightsPage.tsx
      AdminSettingsPage.tsx
    test/
      setup.ts
    __tests__/
      public-pages.test.tsx
      admin-pages.test.tsx
.env.example
README.md
```

Responsibilities:

- `backend/app/api/public.py`: read-only public highlight endpoints.
- `backend/app/api/admin.py`: admin endpoints for sources, jobs, highlights, and settings.
- `backend/app/core/*`: configuration, encryption, database sessions, and scheduler startup.
- `backend/app/models/entities.py`: SQLAlchemy models for the six confirmed tables.
- `backend/app/services/*`: business logic not tied to FastAPI request objects.
- `backend/app/sources/base.py`: stable adapter protocol and raw item draft type.
- `backend/app/sources/xueqiu.py`: Xueqiu parsing and request logic.
- `frontend/src/pages/*`: one route per confirmed public/admin page.

---

### Task 1: Backend Project Skeleton And Secure Config

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/environment.yml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/core/crypto.py`
- Create: `backend/tests/test_crypto.py`
- Create: `.env.example`

- [ ] **Step 1: Write the failing crypto tests**

Create `backend/tests/test_crypto.py`:

```python
import pytest

from app.core.crypto import CryptoService


def test_encrypt_decrypt_roundtrip() -> None:
    service = CryptoService("eHl6MTIzNDU2Nzg5MDEyMzQ1Njc4OTAxMjM0NTY=")

    encrypted = service.encrypt("secret-cookie")

    assert encrypted != "secret-cookie"
    assert service.decrypt(encrypted) == "secret-cookie"


def test_decrypt_empty_value_returns_empty_string() -> None:
    service = CryptoService("eHl6MTIzNDU2Nzg5MDEyMzQ1Njc4OTAxMjM0NTY=")

    assert service.decrypt("") == ""


def test_invalid_key_raises_clear_error() -> None:
    with pytest.raises(ValueError, match="APP_SECRET_KEY must be a urlsafe base64 Fernet key"):
        CryptoService("not-a-fernet-key")
```

- [ ] **Step 2: Add backend dependencies, conda environment, and config skeleton**

Create `backend/pyproject.toml`:

```toml
[project]
name = "today-highlights-backend"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "alembic>=1.13",
  "apscheduler>=3.10",
  "cryptography>=42.0",
  "fastapi>=0.111",
  "httpx>=0.27",
  "pydantic-settings>=2.2",
  "pymysql>=1.1",
  "sqlalchemy>=2.0",
  "uvicorn[standard]>=0.30",
]

[project.optional-dependencies]
test = [
  "pytest>=8.2",
  "pytest-asyncio>=0.23",
]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
asyncio_mode = "auto"
```

Create `backend/environment.yml`:

```yaml
name: today-highlights
channels:
  - conda-forge
dependencies:
  - python=3.11
  - pip
  - pip:
      - -e ".[test]"
```

Create `backend/app/core/config.py`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "mysql+pymysql://daily:daily@127.0.0.1:3306/daily_highlights"
    app_secret_key: str
    cors_origins: str = "http://localhost:5173"
    scheduler_enabled: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
```

- [ ] **Step 3: Implement encryption service**

Create `backend/app/core/crypto.py`:

```python
from cryptography.fernet import Fernet, InvalidToken


class CryptoService:
    def __init__(self, key: str) -> None:
        try:
            self._fernet = Fernet(key.encode("utf-8"))
        except Exception as exc:
            raise ValueError("APP_SECRET_KEY must be a urlsafe base64 Fernet key") from exc

    def encrypt(self, value: str) -> str:
        if value == "":
            return ""
        return self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt(self, value: str) -> str:
        if value == "":
            return ""
        try:
            return self._fernet.decrypt(value.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("Encrypted value cannot be decrypted with the configured key") from exc
```

- [ ] **Step 4: Add FastAPI app entrypoint**

Create `backend/app/main.py`:

```python
from fastapi import FastAPI

app = FastAPI(title="今日看点 API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

Create empty package files:

```text
backend/app/__init__.py
backend/app/core/__init__.py
```

- [ ] **Step 5: Add environment example**

Create `.env.example`:

```dotenv
DATABASE_URL=mysql+pymysql://daily:daily@127.0.0.1:3306/daily_highlights
APP_SECRET_KEY=replace-with-output-from-python-fernet-generate-key
CORS_ORIGINS=http://localhost:5173
SCHEDULER_ENABLED=true
```

- [ ] **Step 6: Run tests**

Run:

```bash
cd backend
pytest tests/test_crypto.py -v
```

Expected: `3 passed`.

- [ ] **Step 7: Commit**

```bash
git add .env.example backend
git commit -m "feat: add backend config and crypto"
```

---

### Task 2: Database Models And Migration

**Files:**
- Create: `backend/app/core/database.py`
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/entities.py`
- Create: `backend/alembic.ini`
- Create: `backend/migrations/env.py`
- Create: `backend/migrations/script.py.mako`
- Create: `backend/migrations/versions/20260520_0001_initial.py`
- Create: `backend/tests/test_models.py`

- [ ] **Step 1: Write model tests**

Create `backend/tests/test_models.py`:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models.entities import Highlight, RawItem, Source, Topic


def test_topic_source_raw_item_highlight_relationships() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        topic = Topic(name="股票", slug="stocks", sort_order=1, enabled=True)
        source = Source(topic=topic, site="xueqiu", name="雪球自选", entry_url="https://xueqiu.com", enabled=True)
        raw = RawItem(source=source, external_id="100", url="https://xueqiu.com/100", title="原文", body="正文")
        highlight = Highlight(topic=topic, raw_item=raw, title="看点", summary="摘要", score=80)
        session.add(highlight)
        session.commit()

        saved = session.query(Highlight).one()
        assert saved.topic.slug == "stocks"
        assert saved.raw_item.source.site == "xueqiu"
```

- [ ] **Step 2: Implement database base and session factory**

Create `backend/app/core/database.py`:

```python
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
```

- [ ] **Step 3: Implement SQLAlchemy entities**

Create `backend/app/models/entities.py` with these models and relationships:

```python
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class Topic(TimestampMixin, Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    sources: Mapped[list["Source"]] = relationship(back_populates="topic")
    highlights: Mapped[list["Highlight"]] = relationship(back_populates="topic")


class Source(TimestampMixin, Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), nullable=False)
    site: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    entry_url: Mapped[str] = mapped_column(String(500), nullable=False)
    cookie_encrypted: Mapped[str] = mapped_column(Text, default="", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    crawl_interval_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    last_crawled_at: Mapped[datetime | None] = mapped_column(DateTime)

    topic: Mapped[Topic] = relationship(back_populates="sources")
    jobs: Mapped[list["CrawlJob"]] = relationship(back_populates="source")
    raw_items: Mapped[list["RawItem"]] = relationship(back_populates="source")


class CrawlJob(Base):
    __tablename__ = "crawl_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    items_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    items_saved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    log_excerpt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    source: Mapped[Source] = relationship(back_populates="jobs")


class RawItem(Base):
    __tablename__ = "raw_items"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_raw_item_external"),
        UniqueConstraint("source_id", "content_hash", name="uq_raw_item_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    author: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    title: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    source: Mapped[Source] = relationship(back_populates="raw_items")
    highlights: Mapped[list["Highlight"]] = relationship(back_populates="raw_item")


class Highlight(TimestampMixin, Base):
    __tablename__ = "highlights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), nullable=False)
    raw_item_id: Mapped[int] = mapped_column(ForeignKey("raw_items.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    related_symbols_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    tags_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    review_status: Mapped[str] = mapped_column(String(30), default="generated", nullable=False)
    generated_by_model: Mapped[str] = mapped_column(String(120), default="", nullable=False)

    topic: Mapped[Topic] = relationship(back_populates="highlights")
    raw_item: Mapped[RawItem] = relationship(back_populates="highlights")


class AppSetting(TimestampMixin, Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    value_encrypted: Mapped[str] = mapped_column(Text, default="", nullable=False)
```

Create `backend/app/models/__init__.py`:

```python
from app.models.entities import AppSetting, CrawlJob, Highlight, RawItem, Source, Topic

__all__ = ["AppSetting", "CrawlJob", "Highlight", "RawItem", "Source", "Topic"]
```

- [ ] **Step 4: Add Alembic configuration**

Create `backend/alembic.ini`, `backend/migrations/env.py`, `backend/migrations/script.py.mako`, and `backend/migrations/versions/20260520_0001_initial.py` using SQLAlchemy metadata from `app.core.database.Base`. The initial migration must create `topics`, `sources`, `crawl_jobs`, `raw_items`, `highlights`, and `app_settings` with the same columns and constraints defined in `entities.py`.

- [ ] **Step 5: Run model tests**

Run:

```bash
cd backend
pytest tests/test_models.py -v
```

Expected: `1 passed`.

- [ ] **Step 6: Commit**

```bash
git add backend
git commit -m "feat: add database models"
```

---

### Task 3: Xueqiu Adapter With Fixture-Based Parsing

**Files:**
- Create: `backend/app/sources/__init__.py`
- Create: `backend/app/sources/base.py`
- Create: `backend/app/sources/xueqiu.py`
- Create: `backend/tests/fixtures/xueqiu_timeline.json`
- Create: `backend/tests/test_xueqiu_adapter.py`

- [ ] **Step 1: Add fixture**

Create `backend/tests/fixtures/xueqiu_timeline.json`:

```json
{
  "list": [
    {
      "id": 12345,
      "target": "/12345",
      "user": { "screen_name": "投资者A" },
      "title": "新能源板块午后走强",
      "text": "新能源板块午后走强，资金关注度明显提升。",
      "created_at": 1779255600000,
      "reply_count": 8,
      "retweet_count": 3,
      "fav_count": 21
    }
  ]
}
```

- [ ] **Step 2: Write adapter tests**

Create `backend/tests/test_xueqiu_adapter.py`:

```python
import json
from pathlib import Path

from app.sources.xueqiu import XueqiuAdapter


def test_parse_timeline_fixture() -> None:
    payload = json.loads(Path("tests/fixtures/xueqiu_timeline.json").read_text())
    items = XueqiuAdapter.parse_timeline(payload)

    assert len(items) == 1
    item = items[0]
    assert item.external_id == "12345"
    assert item.url == "https://xueqiu.com/12345"
    assert item.author == "投资者A"
    assert item.title == "新能源板块午后走强"
    assert item.body == "新能源板块午后走强，资金关注度明显提升。"
    assert item.metrics["fav_count"] == 21
    assert item.content_hash
```

- [ ] **Step 3: Implement adapter protocol and draft type**

Create `backend/app/sources/base.py`:

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class RawItemDraft:
    external_id: str
    url: str
    author: str
    title: str
    body: str
    published_at: datetime | None
    metrics: dict[str, int | str] = field(default_factory=dict)
    content_hash: str = ""


class SourceAdapter(Protocol):
    def fetch(self, entry_url: str, cookie: str) -> list[RawItemDraft]:
        raise NotImplementedError
```

- [ ] **Step 4: Implement Xueqiu parsing and fetch**

Create `backend/app/sources/xueqiu.py`:

```python
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

import httpx

from app.sources.base import RawItemDraft


class XueqiuAdapter:
    base_url = "https://xueqiu.com"

    def fetch(self, entry_url: str, cookie: str) -> list[RawItemDraft]:
        headers = {
            "Cookie": cookie,
            "User-Agent": "Mozilla/5.0 TodayHighlights/0.1",
            "Accept": "application/json,text/plain,*/*",
        }
        with httpx.Client(timeout=15, follow_redirects=True, headers=headers) as client:
            response = client.get(entry_url)
            if response.status_code in {401, 403}:
                raise RuntimeError(f"Xueqiu request rejected with HTTP {response.status_code}")
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "json" not in content_type:
                raise RuntimeError("Xueqiu response is not JSON; Cookie may be expired or page structure changed")
            return self.parse_timeline(response.json())

    @classmethod
    def parse_timeline(cls, payload: dict[str, Any]) -> list[RawItemDraft]:
        rows = payload.get("list", [])
        drafts: list[RawItemDraft] = []
        for row in rows:
            external_id = str(row.get("id", ""))
            target = str(row.get("target", ""))
            url = target if target.startswith("http") else f"{cls.base_url}{target}"
            author = str(row.get("user", {}).get("screen_name", ""))
            title = str(row.get("title") or "").strip()
            body = str(row.get("text") or "").strip()
            created_at_ms = row.get("created_at")
            published_at = None
            if isinstance(created_at_ms, int):
                published_at = datetime.fromtimestamp(created_at_ms / 1000, tz=timezone.utc).replace(tzinfo=None)
            metrics = {
                "reply_count": int(row.get("reply_count") or 0),
                "retweet_count": int(row.get("retweet_count") or 0),
                "fav_count": int(row.get("fav_count") or 0),
            }
            digest = sha256(f"{external_id}|{url}|{title}|{body}".encode("utf-8")).hexdigest()
            drafts.append(
                RawItemDraft(
                    external_id=external_id,
                    url=url,
                    author=author,
                    title=title,
                    body=body,
                    published_at=published_at,
                    metrics=metrics,
                    content_hash=digest,
                )
            )
        return drafts
```

- [ ] **Step 5: Run adapter tests**

Run:

```bash
cd backend
pytest tests/test_xueqiu_adapter.py -v
```

Expected: `1 passed`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/sources backend/tests
git commit -m "feat: add xueqiu adapter"
```

---

### Task 4: Content And Summarizer Services

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/content.py`
- Create: `backend/app/services/summarizer.py`
- Create: `backend/tests/test_content_service.py`
- Create: `backend/tests/test_summarizer.py`

- [ ] **Step 1: Write content service tests**

Create `backend/tests/test_content_service.py`:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.models.entities import Source, Topic
from app.services.content import save_raw_items
from app.sources.base import RawItemDraft


def test_save_raw_items_deduplicates_by_external_id() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as session:
        topic = Topic(name="股票", slug="stocks")
        source = Source(topic=topic, site="xueqiu", name="雪球", entry_url="https://xueqiu.com")
        session.add(source)
        session.commit()

        draft = RawItemDraft(
            external_id="123",
            url="https://xueqiu.com/123",
            author="作者",
            title="标题",
            body="正文",
            published_at=None,
            metrics={"fav_count": 1},
            content_hash="hash-123",
        )

        first = save_raw_items(session, source.id, [draft])
        second = save_raw_items(session, source.id, [draft])

        assert len(first) == 1
        assert second == []
```

- [ ] **Step 2: Implement raw item persistence**

Create `backend/app/services/content.py`:

```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Highlight, RawItem
from app.sources.base import RawItemDraft


def save_raw_items(session: Session, source_id: int, drafts: list[RawItemDraft]) -> list[RawItem]:
    saved: list[RawItem] = []
    for draft in drafts:
        existing = session.scalar(
            select(RawItem).where(
                RawItem.source_id == source_id,
                (RawItem.external_id == draft.external_id) | (RawItem.content_hash == draft.content_hash),
            )
        )
        if existing is not None:
            continue
        item = RawItem(
            source_id=source_id,
            external_id=draft.external_id,
            url=draft.url,
            author=draft.author,
            title=draft.title,
            body=draft.body,
            published_at=draft.published_at,
            metrics_json=draft.metrics,
            content_hash=draft.content_hash,
        )
        session.add(item)
        saved.append(item)
    session.flush()
    return saved


def update_highlight_review(
    session: Session,
    highlight_id: int,
    *,
    title: str,
    summary: str,
    is_pinned: bool,
    is_hidden: bool,
) -> Highlight:
    highlight = session.get(Highlight, highlight_id)
    if highlight is None:
        raise ValueError("Highlight not found")
    highlight.title = title
    highlight.summary = summary
    highlight.is_pinned = is_pinned
    highlight.is_hidden = is_hidden
    highlight.review_status = "reviewed"
    session.flush()
    return highlight
```

- [ ] **Step 3: Write summarizer tests**

Create `backend/tests/test_summarizer.py`:

```python
import pytest

from app.services.summarizer import HighlightDraft, SummarizerClient


@pytest.mark.asyncio
async def test_summarizer_parses_json_response() -> None:
    async def fake_post(payload: dict) -> dict:
        return {
            "choices": [
                {
                    "message": {
                        "content": "{\"title\":\"资金关注新能源\",\"summary\":\"新能源板块热度上升。\",\"related_symbols\":[\"新能源\"],\"tags\":[\"资金\"],\"score\":82}"
                    }
                }
            ]
        }

    client = SummarizerClient("https://api.example.com/v1", "key", "model", post_json=fake_post)
    result = await client.summarize("标题", "正文")

    assert result == HighlightDraft(
        title="资金关注新能源",
        summary="新能源板块热度上升。",
        related_symbols=["新能源"],
        tags=["资金"],
        score=82,
    )
```

- [ ] **Step 4: Implement summarizer client**

Create `backend/app/services/summarizer.py`:

```python
import json
from dataclasses import dataclass
from typing import Awaitable, Callable

import httpx


@dataclass(frozen=True)
class HighlightDraft:
    title: str
    summary: str
    related_symbols: list[str]
    tags: list[str]
    score: int


PostJson = Callable[[dict], Awaitable[dict]]


class SummarizerClient:
    def __init__(self, base_url: str, api_key: str, model: str, post_json: PostJson | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self._post_json = post_json

    async def summarize(self, title: str, body: str) -> HighlightDraft:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "你是股票信息摘要助手，只输出 JSON。"},
                {
                    "role": "user",
                    "content": (
                        "基于以下雪球内容生成今日看点。输出字段：title, summary, "
                        "related_symbols, tags, score。"
                        f"\n标题：{title}\n正文：{body}"
                    ),
                },
            ],
            "temperature": 0.2,
        }
        response = await self._send(payload)
        content = response["choices"][0]["message"]["content"]
        data = json.loads(content)
        return HighlightDraft(
            title=str(data["title"]),
            summary=str(data["summary"]),
            related_symbols=[str(item) for item in data.get("related_symbols", [])],
            tags=[str(item) for item in data.get("tags", [])],
            score=int(data.get("score", 0)),
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

- [ ] **Step 5: Run service tests**

Run:

```bash
cd backend
pytest tests/test_content_service.py tests/test_summarizer.py -v
```

Expected: `2 passed`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services backend/tests
git commit -m "feat: add content and summarizer services"
```

---

### Task 5: Admin And Public APIs

**Files:**
- Create: `backend/app/schemas/__init__.py`
- Create: `backend/app/schemas/admin.py`
- Create: `backend/app/schemas/public.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/admin.py`
- Create: `backend/app/api/public.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_admin_api.py`
- Create: `backend/tests/test_public_api.py`

- [ ] **Step 1: Write API tests for sensitive field masking**

Create `backend/tests/test_admin_api.py`:

```python
from fastapi.testclient import TestClient

from app.main import app


def test_health_route() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

Create `backend/tests/test_public_api.py`:

```python
from fastapi.testclient import TestClient

from app.main import app


def test_public_topics_route_exists() -> None:
    client = TestClient(app)
    response = client.get("/api/public/topics")
    assert response.status_code in {200, 500}
```

- [ ] **Step 2: Add schemas**

Create `backend/app/schemas/admin.py` with Pydantic request and response models:

```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SourceCreate(BaseModel):
    topic_id: int
    site: str
    name: str
    entry_url: str
    cookie: str = ""
    enabled: bool = True
    crawl_interval_minutes: int = 60


class SourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    topic_id: int
    site: str
    name: str
    entry_url: str
    enabled: bool
    crawl_interval_minutes: int
    last_crawled_at: datetime | None
    has_cookie: bool


class HighlightUpdate(BaseModel):
    title: str
    summary: str
    is_pinned: bool
    is_hidden: bool
```

Create `backend/app/schemas/public.py`:

```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TopicRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    sort_order: int


class HighlightRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    summary: str
    related_symbols_json: list[str]
    tags_json: list[str]
    score: int
    is_pinned: bool
    created_at: datetime
```

- [ ] **Step 3: Add routes**

Create `backend/app/api/public.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.models.entities import Highlight, Topic
from app.schemas.public import HighlightRead, TopicRead

router = APIRouter(prefix="/api/public", tags=["public"])


@router.get("/topics", response_model=list[TopicRead])
def list_topics(session: Session = Depends(get_session)) -> list[Topic]:
    return list(session.scalars(select(Topic).where(Topic.enabled.is_(True)).order_by(Topic.sort_order)))


@router.get("/highlights", response_model=list[HighlightRead])
def list_highlights(session: Session = Depends(get_session)) -> list[Highlight]:
    statement = (
        select(Highlight)
        .where(Highlight.is_hidden.is_(False))
        .order_by(Highlight.is_pinned.desc(), Highlight.score.desc(), Highlight.created_at.desc())
    )
    return list(session.scalars(statement))
```

Create `backend/app/api/admin.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import CryptoService
from app.core.database import get_session
from app.models.entities import CrawlJob, Highlight, Source
from app.schemas.admin import HighlightUpdate, SourceCreate, SourceRead
from app.services.content import update_highlight_review

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/sources", response_model=list[SourceRead])
def list_sources(session: Session = Depends(get_session)) -> list[dict]:
    sources = session.scalars(select(Source).order_by(Source.id.desc())).all()
    return [
        {
            "id": source.id,
            "topic_id": source.topic_id,
            "site": source.site,
            "name": source.name,
            "entry_url": source.entry_url,
            "enabled": source.enabled,
            "crawl_interval_minutes": source.crawl_interval_minutes,
            "last_crawled_at": source.last_crawled_at,
            "has_cookie": bool(source.cookie_encrypted),
        }
        for source in sources
    ]


@router.post("/sources", response_model=SourceRead)
def create_source(payload: SourceCreate, session: Session = Depends(get_session)) -> dict:
    crypto = CryptoService(settings.app_secret_key)
    source = Source(
        topic_id=payload.topic_id,
        site=payload.site,
        name=payload.name,
        entry_url=payload.entry_url,
        cookie_encrypted=crypto.encrypt(payload.cookie),
        enabled=payload.enabled,
        crawl_interval_minutes=payload.crawl_interval_minutes,
    )
    session.add(source)
    session.commit()
    session.refresh(source)
    return {
        "id": source.id,
        "topic_id": source.topic_id,
        "site": source.site,
        "name": source.name,
        "entry_url": source.entry_url,
        "enabled": source.enabled,
        "crawl_interval_minutes": source.crawl_interval_minutes,
        "last_crawled_at": source.last_crawled_at,
        "has_cookie": bool(source.cookie_encrypted),
    }


@router.get("/jobs")
def list_jobs(session: Session = Depends(get_session)) -> list[dict]:
    jobs = session.scalars(select(CrawlJob).order_by(CrawlJob.created_at.desc()).limit(50)).all()
    return [
        {
            "id": job.id,
            "source_id": job.source_id,
            "trigger_type": job.trigger_type,
            "status": job.status,
            "items_found": job.items_found,
            "items_saved": job.items_saved,
            "error_message": job.error_message,
            "log_excerpt": job.log_excerpt,
            "started_at": job.started_at,
            "finished_at": job.finished_at,
        }
        for job in jobs
    ]


@router.patch("/highlights/{highlight_id}")
def update_highlight(highlight_id: int, payload: HighlightUpdate, session: Session = Depends(get_session)) -> dict:
    highlight = update_highlight_review(
        session,
        highlight_id,
        title=payload.title,
        summary=payload.summary,
        is_pinned=payload.is_pinned,
        is_hidden=payload.is_hidden,
    )
    session.commit()
    return {"id": highlight.id, "review_status": highlight.review_status}
```

Modify `backend/app/main.py`:

```python
from fastapi import FastAPI

from app.api import admin, public

app = FastAPI(title="今日看点 API")
app.include_router(public.router)
app.include_router(admin.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 4: Run API tests**

Run:

```bash
cd backend
pytest tests/test_admin_api.py tests/test_public_api.py -v
```

Expected: tests pass or fail only because the test database is not configured. If database setup fails, add dependency overrides in tests to use an in-memory SQLite session, then rerun until both tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api backend/app/schemas backend/app/main.py backend/tests
git commit -m "feat: add public and admin APIs"
```

---

### Task 6: Crawl Job Orchestration And Scheduler

**Files:**
- Create: `backend/app/services/jobs.py`
- Create: `backend/app/core/scheduler.py`
- Modify: `backend/app/api/admin.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Add job service**

Create `backend/app/services/jobs.py`:

```python
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import CryptoService
from app.models.entities import CrawlJob, Highlight, Source
from app.services.content import save_raw_items
from app.services.summarizer import HighlightDraft
from app.sources.xueqiu import XueqiuAdapter


def run_crawl_job(session: Session, source_id: int, trigger_type: str) -> CrawlJob:
    running = session.scalar(
        select(CrawlJob).where(CrawlJob.source_id == source_id, CrawlJob.status == "running")
    )
    if running is not None:
        return running

    source = session.get(Source, source_id)
    if source is None:
        raise ValueError("Source not found")

    job = CrawlJob(source_id=source_id, trigger_type=trigger_type, status="running", started_at=datetime.utcnow())
    session.add(job)
    session.flush()

    try:
        cookie = CryptoService(settings.app_secret_key).decrypt(source.cookie_encrypted)
        adapter = XueqiuAdapter()
        drafts = adapter.fetch(source.entry_url, cookie)
        raw_items = save_raw_items(session, source.id, drafts)
        for raw_item in raw_items:
            summary = HighlightDraft(
                title=raw_item.title or "雪球看点",
                summary=raw_item.body[:200],
                related_symbols=[],
                tags=["雪球"],
                score=int(raw_item.metrics_json.get("fav_count", 0)),
            )
            session.add(
                Highlight(
                    topic_id=source.topic_id,
                    raw_item_id=raw_item.id,
                    title=summary.title,
                    summary=summary.summary,
                    related_symbols_json=summary.related_symbols,
                    tags_json=summary.tags,
                    score=summary.score,
                    generated_by_model="fallback-sync",
                )
            )
        job.status = "success"
        job.items_found = len(drafts)
        job.items_saved = len(raw_items)
        job.finished_at = datetime.utcnow()
        source.last_crawled_at = job.finished_at
    except Exception as exc:
        job.status = "failed"
        job.error_message = str(exc)
        job.log_excerpt = str(exc)[:500]
        job.finished_at = datetime.utcnow()
    session.commit()
    return job
```

This first orchestration stores fallback highlights. Replace fallback summary creation with the real `SummarizerClient` in the next task so job wiring can be verified independently.

- [ ] **Step 2: Add manual trigger route**

Modify `backend/app/api/admin.py` to add:

```python
from app.services.jobs import run_crawl_job


@router.post("/sources/{source_id}/crawl")
def trigger_crawl(source_id: int, session: Session = Depends(get_session)) -> dict:
    job = run_crawl_job(session, source_id, "manual")
    return {"id": job.id, "status": job.status, "items_found": job.items_found, "items_saved": job.items_saved}
```

- [ ] **Step 3: Add scheduler module**

Create `backend/app/core/scheduler.py`:

```python
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.entities import Source
from app.services.jobs import run_crawl_job


def crawl_enabled_sources() -> None:
    with SessionLocal() as session:
        sources = session.scalars(select(Source).where(Source.enabled.is_(True))).all()
        for source in sources:
            run_crawl_job(session, source.id, "scheduled")


def create_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    scheduler.add_job(crawl_enabled_sources, "interval", minutes=5, id="crawl_enabled_sources", replace_existing=True)
    return scheduler
```

- [ ] **Step 4: Start scheduler on app startup**

Modify `backend/app/main.py`:

```python
from fastapi import FastAPI

from app.api import admin, public
from app.core.config import settings
from app.core.scheduler import create_scheduler

app = FastAPI(title="今日看点 API")
app.include_router(public.router)
app.include_router(admin.router)


@app.on_event("startup")
def start_scheduler() -> None:
    if settings.scheduler_enabled:
        scheduler = create_scheduler()
        scheduler.start()
        app.state.scheduler = scheduler


@app.on_event("shutdown")
def stop_scheduler() -> None:
    scheduler = getattr(app.state, "scheduler", None)
    if scheduler is not None:
        scheduler.shutdown(wait=False)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 5: Run backend tests**

Run:

```bash
cd backend
pytest -v
```

Expected: all existing backend tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app
git commit -m "feat: add crawl job orchestration"
```

---

### Task 7: Real AI Settings And Summary Integration

**Files:**
- Create: `backend/app/services/settings.py`
- Modify: `backend/app/services/jobs.py`
- Modify: `backend/app/api/admin.py`

- [ ] **Step 1: Implement settings service**

Create `backend/app/services/settings.py`:

```python
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import CryptoService
from app.models.entities import AppSetting


def set_plain_setting(session: Session, key: str, value: str) -> None:
    setting = session.get(AppSetting, key) or AppSetting(key=key)
    setting.value_json = {"value": value}
    session.add(setting)


def get_plain_setting(session: Session, key: str, default: str = "") -> str:
    setting = session.get(AppSetting, key)
    if setting is None or setting.value_json is None:
        return default
    return str(setting.value_json.get("value", default))


def set_secret_setting(session: Session, key: str, value: str) -> None:
    setting = session.get(AppSetting, key) or AppSetting(key=key)
    setting.value_encrypted = CryptoService(settings.app_secret_key).encrypt(value)
    session.add(setting)


def get_secret_setting(session: Session, key: str) -> str:
    setting = session.get(AppSetting, key)
    if setting is None:
        return ""
    return CryptoService(settings.app_secret_key).decrypt(setting.value_encrypted)
```

- [ ] **Step 2: Add model settings routes**

Modify `backend/app/api/admin.py` to add:

```python
from pydantic import BaseModel

from app.services.settings import get_plain_setting, get_secret_setting, set_plain_setting, set_secret_setting


class ModelSettingsWrite(BaseModel):
    base_url: str
    api_key: str = ""
    model: str


@router.get("/settings/model")
def read_model_settings(session: Session = Depends(get_session)) -> dict:
    return {
        "base_url": get_plain_setting(session, "llm.base_url"),
        "model": get_plain_setting(session, "llm.model"),
        "has_api_key": bool(get_secret_setting(session, "llm.api_key")),
    }


@router.put("/settings/model")
def write_model_settings(payload: ModelSettingsWrite, session: Session = Depends(get_session)) -> dict:
    set_plain_setting(session, "llm.base_url", payload.base_url)
    set_plain_setting(session, "llm.model", payload.model)
    if payload.api_key:
        set_secret_setting(session, "llm.api_key", payload.api_key)
    session.commit()
    return {"saved": True, "has_api_key": bool(payload.api_key)}
```

- [ ] **Step 3: Use real summarizer when configured**

Modify `backend/app/services/jobs.py` so raw items call `SummarizerClient` when all model settings exist. Keep fallback summary when settings are incomplete or the model call fails, and set `review_status` to `ai_failed` on failures.

The generated highlight block should use this shape:

```python
model_name = get_plain_setting(session, "llm.model")
base_url = get_plain_setting(session, "llm.base_url")
api_key = get_secret_setting(session, "llm.api_key")
```

When all three values are present, call:

```python
summary = await SummarizerClient(base_url, api_key, model_name).summarize(raw_item.title, raw_item.body)
```

If keeping `run_crawl_job` synchronous, wrap the async call with:

```python
import asyncio

summary = asyncio.run(SummarizerClient(base_url, api_key, model_name).summarize(raw_item.title, raw_item.body))
```

- [ ] **Step 4: Run backend tests**

Run:

```bash
cd backend
pytest -v
```

Expected: all backend tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app
git commit -m "feat: add model settings and ai summaries"
```

---

### Task 8: Frontend Shell, API Client, And Public Pages

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/api/types.ts`
- Create: `frontend/src/pages/SummaryPage.tsx`
- Create: `frontend/src/pages/StockTopicPage.tsx`
- Create: `frontend/src/test/setup.ts`
- Create: `frontend/src/__tests__/public-pages.test.tsx`

- [ ] **Step 1: Create Vite React package**

Create `frontend/package.json`:

```json
{
  "name": "today-highlights-frontend",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "test": "vitest run"
  },
  "dependencies": {
    "@tanstack/react-query": "^5.40.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.23.0"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.4.0",
    "@testing-library/react": "^15.0.0",
    "@testing-library/user-event": "^14.5.0",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.2.0",
    "typescript": "^5.4.0",
    "vite": "^5.2.0",
    "vitest": "^1.6.0"
  }
}
```

Create standard Vite files:

```html
<!-- frontend/index.html -->
<div id="root"></div>
<script type="module" src="/src/main.tsx"></script>
```

```json
// frontend/tsconfig.json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["DOM", "DOM.Iterable", "ES2020"],
    "allowJs": false,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "module": "ESNext",
    "moduleResolution": "Node",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx"
  },
  "include": ["src"]
}
```

```ts
// frontend/vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
  },
});
```

- [ ] **Step 2: Add API types and client**

Create `frontend/src/api/types.ts`:

```ts
export interface Highlight {
  id: number;
  title: string;
  summary: string;
  related_symbols_json: string[];
  tags_json: string[];
  score: number;
  is_pinned: boolean;
  created_at: string;
}

export interface Topic {
  id: number;
  name: string;
  slug: string;
  sort_order: number;
}
```

Create `frontend/src/api/client.ts`:

```ts
import type { Highlight, Topic } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function fetchTopics(): Promise<Topic[]> {
  return getJson<Topic[]>("/api/public/topics");
}

export function fetchHighlights(): Promise<Highlight[]> {
  return getJson<Highlight[]>("/api/public/highlights");
}
```

- [ ] **Step 3: Add app shell and public pages**

Create `frontend/src/App.tsx` with routes for `/`, `/topics/stocks`, and admin route paths. Create `SummaryPage.tsx` to render highlight cards from `fetchHighlights`. Create `StockTopicPage.tsx` to render the same highlights with a stock-focused heading and tag/symbol chips.

Use CSS in the component files or a small `src/styles.css`. Keep the UI dense and readable: top navigation, constrained content width, compact cards, visible source metadata sections.

- [ ] **Step 4: Add public page test**

Create `frontend/src/__tests__/public-pages.test.tsx` that mocks `global.fetch` and verifies:

```ts
expect(await screen.findByText("资金关注新能源")).toBeInTheDocument();
expect(screen.getByText("新能源板块热度上升。")).toBeInTheDocument();
```

- [ ] **Step 5: Run frontend public tests**

Run:

```bash
cd frontend
npm install
npm test -- public-pages.test.tsx
```

Expected: public page tests pass.

- [ ] **Step 6: Commit**

```bash
git add frontend
git commit -m "feat: add frontend public pages"
```

---

### Task 9: Frontend Admin Pages

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/types.ts`
- Create: `frontend/src/pages/AdminSourcesPage.tsx`
- Create: `frontend/src/pages/AdminJobsPage.tsx`
- Create: `frontend/src/pages/AdminHighlightsPage.tsx`
- Create: `frontend/src/pages/AdminSettingsPage.tsx`
- Create: `frontend/src/__tests__/admin-pages.test.tsx`

- [ ] **Step 1: Add admin API types and functions**

Extend `frontend/src/api/types.ts` with:

```ts
export interface Source {
  id: number;
  topic_id: number;
  site: string;
  name: string;
  entry_url: string;
  enabled: boolean;
  crawl_interval_minutes: number;
  last_crawled_at: string | null;
  has_cookie: boolean;
}

export interface CrawlJob {
  id: number;
  source_id: number;
  trigger_type: string;
  status: string;
  items_found: number;
  items_saved: number;
  error_message: string;
  log_excerpt: string;
  started_at: string | null;
  finished_at: string | null;
}
```

Extend `frontend/src/api/client.ts` with `fetchSources`, `createSource`, `triggerCrawl`, `fetchJobs`, `saveModelSettings`, and `fetchModelSettings`.

- [ ] **Step 2: Build admin pages**

Implement:

- `AdminSourcesPage.tsx`: form for topic id, site, name, entry URL, Cookie, enabled flag, interval, source list, and immediate crawl button.
- `AdminJobsPage.tsx`: table with job status, trigger type, found count, saved count, error message, and time.
- `AdminHighlightsPage.tsx`: editable title/summary controls, pin checkbox, hide checkbox, save button.
- `AdminSettingsPage.tsx`: base URL, model, API key input, save button, and has-key state.

- [ ] **Step 3: Add admin page tests**

Create `frontend/src/__tests__/admin-pages.test.tsx` to verify:

```ts
expect(await screen.findByText("数据源管理")).toBeInTheDocument();
expect(screen.getByLabelText("雪球入口 URL")).toBeInTheDocument();
expect(screen.getByLabelText("Cookie")).toBeInTheDocument();
```

and:

```ts
expect(await screen.findByText("任务日志")).toBeInTheDocument();
expect(screen.getByText("success")).toBeInTheDocument();
```

- [ ] **Step 4: Run frontend admin tests**

Run:

```bash
cd frontend
npm test -- admin-pages.test.tsx
```

Expected: admin page tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend
git commit -m "feat: add frontend admin pages"
```

---

### Task 10: Documentation And End-To-End Verification

**Files:**
- Create: `README.md`
- Modify: `.env.example`

- [ ] **Step 1: Write README**

Create `README.md` with:

```markdown
# 今日看点

今日看点 is a Python + React MVP for collecting Xueqiu stock content, generating AI summaries, and reviewing highlights for a daily reading page.

## Backend

```bash
cd backend
conda env create -f environment.yml
conda activate today-highlights
alembic upgrade head
uvicorn app.main:app --reload
```

For an existing environment, update it with:

```bash
cd backend
conda env update -f environment.yml --prune
conda activate today-highlights
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

## Required Environment

Copy `.env.example` to `.env` and set:

- `DATABASE_URL`
- `APP_SECRET_KEY`
- `CORS_ORIGINS`
- `SCHEDULER_ENABLED`

Generate a Fernet key with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## MVP Scope

- Xueqiu source adapter with manual Cookie configuration.
- MySQL persistence.
- Manual and scheduled crawls.
- OpenAI-compatible AI summaries.
- Public summary and stock pages.
- Admin source, job, highlight, and model settings pages.

The system does not automate login, solve captchas, or bypass anti-bot controls.
```

- [ ] **Step 2: Run full backend verification**

Run:

```bash
cd backend
pytest -v
```

Expected: all backend tests pass.

- [ ] **Step 3: Run full frontend verification**

Run:

```bash
cd frontend
npm test
npm run build
```

Expected: tests pass and production build completes.

- [ ] **Step 4: Start local servers for smoke test**

Run backend:

```bash
cd backend
uvicorn app.main:app --reload
```

Run frontend:

```bash
cd frontend
npm run dev
```

Smoke test:

- Open `http://localhost:5173`.
- Confirm the summary page loads.
- Open `/admin/sources`.
- Confirm the source form loads.
- Open `http://localhost:8000/health`.
- Confirm the response is `{"status":"ok"}`.

- [ ] **Step 5: Commit**

```bash
git add README.md .env.example
git commit -m "docs: add development instructions"
```

---

## Self-Review Checklist

- Spec coverage:
  - Xueqiu stock source: Tasks 3 and 6.
  - Manual Cookie: Tasks 1, 5, and 9.
  - MySQL data model: Task 2.
  - AI summaries with OpenAI-compatible API: Tasks 4 and 7.
  - Public summary and stock detail pages: Task 8.
  - Admin source, job, content, and model pages: Tasks 5, 6, 7, and 9.
  - Testing and startup docs: Task 10.
- Sensitive data:
  - Cookie and API key are encrypted and read APIs expose only configured states.
- Scope discipline:
  - No automatic login, captcha solving, proxy pool, distributed worker, or multi-user auth is included.
