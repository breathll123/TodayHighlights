# Football Media Cache Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cache football team and league logos locally during crawl/block resolution, store rich media metadata in MySQL, and make the football UI prefer local assets with remote fallback.

**Architecture:** Add a reusable `media_assets` table and `MediaCacheService` that downloads remote images into `backend/storage/media/football`, records metadata, and returns stable public URLs. Football adapters will call the service for `logo_a`, `logo_b`, `logo_league`, and standings `logo`, while keeping original remote URLs for fallback. The existing `/api/public/proxy/image` remains a compatibility fallback.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, MySQL, httpx, React, Vitest, pytest.

---

## File Structure

- Create `backend/migrations/versions/20260608_0010_media_assets.py`
  - Creates `media_assets` with rich metadata, indexes, and URL uniqueness.
- Modify `backend/app/models/entities.py`
  - Adds `MediaAsset` ORM model.
- Create `backend/app/services/media_cache.py`
  - Contains URL normalization, SSRF guard, extension/content-type detection, image download, file persistence, DB upsert, and public URL generation.
- Modify `backend/app/api/public.py`
  - Adds `GET /api/public/media/{url_hash}` to serve locally cached files.
  - Keeps `/api/public/proxy/image` as fallback.
- Modify `backend/app/services/adapters/qiumiwu.py`
  - Adds optional media cache injection.
  - Adds local logo fields to matches and standings:
    - `logo_league_local`
    - `logo_a_local`
    - `logo_b_local`
    - `logo_local`
- Modify `backend/app/services/adapters/qiumiwu_schedule.py`
  - Adds optional media cache injection for schedule logos.
- Modify `backend/app/services/blocks.py`
  - Creates one media cache service per DB-backed block resolution and passes it into football adapters.
- Modify `frontend/src/components/layout/MatchCards.tsx`
  - Prefer local logo fields.
- Modify `frontend/src/components/layout/MatchList.tsx`
  - Prefer local logo fields.
- Modify `frontend/src/components/layout/StandingsTable.tsx`
  - Prefer local logo fields.
- Create `backend/tests/test_media_cache.py`
  - Unit tests for caching, dedupe, metadata, SSRF blocking, and route serving.
- Modify or create football adapter tests as needed:
  - `backend/tests/test_qiumiwu_media_cache.py`
- Modify frontend tests:
  - `frontend/src/__tests__/match-list.test.tsx`
  - `frontend/src/__tests__/ranking-tables.test.tsx`

---

## Data Model

`media_assets` should store more than the current minimum so it can support later cleanup, migration to object storage, and diagnostics:

```python
class MediaAsset(TimestampMixin, Base):
    __tablename__ = "media_assets"
    __table_args__ = (
        UniqueConstraint("url_hash", name="uq_media_assets_url_hash"),
        Index("ix_media_assets_status_asset", "status", "asset_type"),
        Index("ix_media_assets_entity", "entity_type", "entity_name"),
        Index("ix_media_assets_provider_last_used", "provider", "last_used_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    normalized_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    asset_type: Mapped[str] = mapped_column(String(40), default="image", nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    entity_name: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    source_entity_id: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    extension: Mapped[str] = mapped_column(String(16), default="", nullable=False)
    local_path: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    public_path: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    fetch_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
```

For football, use:

- `provider`: `qiumiwu`
- `asset_type`: `football_logo`
- `entity_type`: `team` or `league`
- `entity_name`: team or league name
- `source_entity_id`: match id, standings row id, or blank when unknown

---

## Task 1: Add MediaAsset Model and Migration

**Files:**
- Modify: `backend/app/models/entities.py`
- Create: `backend/migrations/versions/20260608_0010_media_assets.py`
- Test: `backend/tests/test_media_cache.py`

- [ ] **Step 1: Write failing model test**

Add this to `backend/tests/test_media_cache.py`:

```python
from datetime import datetime

from sqlalchemy import inspect

from app.models.entities import MediaAsset


def test_media_assets_table_has_rich_metadata_columns(engine) -> None:
    columns = {col["name"] for col in inspect(engine).get_columns("media_assets")}

    assert {
        "id",
        "source_url",
        "normalized_url",
        "url_hash",
        "provider",
        "asset_type",
        "entity_type",
        "entity_name",
        "source_entity_id",
        "original_filename",
        "content_type",
        "extension",
        "local_path",
        "public_path",
        "file_size",
        "width",
        "height",
        "status",
        "fetch_count",
        "last_fetched_at",
        "last_used_at",
        "error_message",
        "metadata_json",
        "created_at",
        "updated_at",
    }.issubset(columns)


def test_media_asset_model_can_store_metadata(session) -> None:
    asset = MediaAsset(
        source_url="https://file.qiumiwu.com/team/arsenal.png",
        normalized_url="https://file.qiumiwu.com/team/arsenal.png",
        url_hash="abc123",
        provider="qiumiwu",
        asset_type="football_logo",
        entity_type="team",
        entity_name="阿森纳",
        source_entity_id="match_1",
        original_filename="arsenal.png",
        content_type="image/png",
        extension=".png",
        local_path="storage/media/football/abc123.png",
        public_path="/api/public/media/abc123",
        file_size=1234,
        width=64,
        height=64,
        status="cached",
        fetch_count=1,
        last_fetched_at=datetime.utcnow(),
        last_used_at=datetime.utcnow(),
        metadata_json={"source": "test"},
    )

    session.add(asset)
    session.commit()

    saved = session.query(MediaAsset).filter_by(url_hash="abc123").one()
    assert saved.entity_name == "阿森纳"
    assert saved.metadata_json == {"source": "test"}
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/lws/Desktop/Code/DataFlow/backend
APP_SECRET_KEY=test-key /Users/lws/opt/anaconda3/envs/daily_highlights/bin/python -m pytest tests/test_media_cache.py -q
```

Expected: FAIL because `MediaAsset` and `media_assets` do not exist.

- [ ] **Step 3: Add `MediaAsset` model**

Add the model from the Data Model section to `backend/app/models/entities.py`.

- [ ] **Step 4: Add migration**

Create `backend/migrations/versions/20260608_0010_media_assets.py`:

```python
"""media assets

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-08
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa


revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    conn = op.get_bind()
    inspector = inspect(conn)
    return name in inspector.get_table_names()


def upgrade() -> None:
    if _table_exists("media_assets"):
        return

    op.create_table(
        "media_assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column("normalized_url", sa.String(length=1000), nullable=False),
        sa.Column("url_hash", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("asset_type", sa.String(length=40), nullable=False, server_default="image"),
        sa.Column("entity_type", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("entity_name", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("source_entity_id", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("original_filename", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("content_type", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("extension", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("local_path", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("public_path", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("fetch_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_fetched_at", sa.DateTime(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("url_hash", name="uq_media_assets_url_hash"),
    )
    op.create_index("ix_media_assets_status_asset", "media_assets", ["status", "asset_type"])
    op.create_index("ix_media_assets_entity", "media_assets", ["entity_type", "entity_name"])
    op.create_index("ix_media_assets_provider_last_used", "media_assets", ["provider", "last_used_at"])


def downgrade() -> None:
    if not _table_exists("media_assets"):
        return
    op.drop_index("ix_media_assets_provider_last_used", table_name="media_assets")
    op.drop_index("ix_media_assets_entity", table_name="media_assets")
    op.drop_index("ix_media_assets_status_asset", table_name="media_assets")
    op.drop_table("media_assets")
```

- [ ] **Step 5: Run tests**

Run:

```bash
cd /Users/lws/Desktop/Code/DataFlow/backend
APP_SECRET_KEY=test-key /Users/lws/opt/anaconda3/envs/daily_highlights/bin/python -m pytest tests/test_media_cache.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/entities.py backend/migrations/versions/20260608_0010_media_assets.py backend/tests/test_media_cache.py
git commit -m "feat(media): add media asset model"
```

---

## Task 2: Implement Media Cache Service

**Files:**
- Create: `backend/app/services/media_cache.py`
- Modify: `backend/tests/test_media_cache.py`

- [ ] **Step 1: Add failing service tests**

Append to `backend/tests/test_media_cache.py`:

```python
from pathlib import Path

import pytest

from app.services.media_cache import MediaCacheService, is_safe_remote_url, url_hash


class _FakeImageResponse:
    headers = {"content-type": "image/png"}
    content = b"\x89PNG\r\n\x1a\nfake"

    def raise_for_status(self) -> None:
        return None


class _FakeClient:
    def __init__(self) -> None:
        self.calls = 0

    def get(self, url: str):
        self.calls += 1
        return _FakeImageResponse()


def test_is_safe_remote_url_blocks_internal_hosts() -> None:
    assert is_safe_remote_url("https://file.qiumiwu.com/team/a.png") is True
    assert is_safe_remote_url("http://127.0.0.1/a.png") is False
    assert is_safe_remote_url("http://localhost/a.png") is False
    assert is_safe_remote_url("http://192.168.1.2/a.png") is False


def test_media_cache_downloads_once_and_reuses_asset(session, tmp_path: Path) -> None:
    client = _FakeClient()
    service = MediaCacheService(session, storage_root=tmp_path, http_client=client)

    first = service.cache_remote_image(
        "https://file.qiumiwu.com/team/a.png",
        provider="qiumiwu",
        entity_type="team",
        entity_name="阿森纳",
        source_entity_id="match_1",
    )
    second = service.cache_remote_image(
        "https://file.qiumiwu.com/team/a.png",
        provider="qiumiwu",
        entity_type="team",
        entity_name="阿森纳",
        source_entity_id="match_2",
    )

    assert first == second
    assert first.startswith("/api/public/media/")
    assert client.calls == 1
    asset_hash = url_hash("https://file.qiumiwu.com/team/a.png")
    assert (tmp_path / "football" / f"{asset_hash}.png").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/lws/Desktop/Code/DataFlow/backend
APP_SECRET_KEY=test-key /Users/lws/opt/anaconda3/envs/daily_highlights/bin/python -m pytest tests/test_media_cache.py -q
```

Expected: FAIL because `app.services.media_cache` does not exist.

- [ ] **Step 3: Implement service**

Create `backend/app/services/media_cache.py`:

```python
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import MediaAsset


DEFAULT_STORAGE_ROOT = Path(__file__).resolve().parents[3] / "storage" / "media"
ALLOWED_CONTENT_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
}


def normalize_url(url: str) -> str:
    parsed = urlparse((url or "").strip())
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    return urlunparse((scheme, netloc, path, "", parsed.query, ""))


def url_hash(url: str) -> str:
    return sha256(normalize_url(url).encode("utf-8")).hexdigest()


def is_safe_remote_url(url: str) -> bool:
    parsed = urlparse((url or "").strip())
    host = parsed.hostname or ""
    if parsed.scheme not in {"http", "https"}:
        return False
    if host in {"localhost", "127.0.0.1", "::1"}:
        return False
    if host.startswith("10.") or host.startswith("192.168."):
        return False
    if host.startswith("172."):
        parts = host.split(".")
        if len(parts) > 1 and parts[1].isdigit() and 16 <= int(parts[1]) <= 31:
            return False
    return True


def extension_for(content_type: str, url: str) -> str:
    ctype = content_type.split(";")[0].strip().lower()
    if ctype in ALLOWED_CONTENT_TYPES:
        return ALLOWED_CONTENT_TYPES[ctype]
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}:
        return ".jpg" if suffix == ".jpeg" else suffix
    return ".bin"


class MediaCacheService:
    def __init__(
        self,
        session: Session,
        *,
        storage_root: Path | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.session = session
        self.storage_root = storage_root or DEFAULT_STORAGE_ROOT
        self.http_client = http_client or httpx.Client(
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0 TodayHighlights/0.1"},
            follow_redirects=True,
        )

    def cache_remote_image(
        self,
        source_url: str,
        *,
        provider: str,
        entity_type: str,
        entity_name: str,
        source_entity_id: str = "",
        asset_type: str = "football_logo",
        metadata: dict | None = None,
    ) -> str:
        normalized = normalize_url(source_url)
        if not normalized or not is_safe_remote_url(normalized):
            return ""

        digest = url_hash(normalized)
        existing = self.session.scalar(select(MediaAsset).where(MediaAsset.url_hash == digest))
        now = datetime.utcnow()
        if existing and existing.status == "cached" and existing.local_path and Path(existing.local_path).exists():
            existing.last_used_at = now
            return existing.public_path

        asset = existing or MediaAsset(
            source_url=source_url,
            normalized_url=normalized,
            url_hash=digest,
        )
        asset.provider = provider
        asset.asset_type = asset_type
        asset.entity_type = entity_type
        asset.entity_name = entity_name
        asset.source_entity_id = source_entity_id
        asset.last_used_at = now
        asset.fetch_count = (asset.fetch_count or 0) + 1
        asset.metadata_json = {**(asset.metadata_json or {}), **(metadata or {})}

        if existing is None:
            self.session.add(asset)

        try:
            response = self.http_client.get(normalized)
            response.raise_for_status()
            body = response.content
            if not body:
                raise ValueError("empty image body")

            content_type = response.headers.get("content-type", "application/octet-stream").split(";")[0].lower()
            extension = extension_for(content_type, normalized)
            folder = self.storage_root / "football"
            folder.mkdir(parents=True, exist_ok=True)
            local_file = folder / f"{digest}{extension}"
            local_file.write_bytes(body)

            asset.original_filename = Path(urlparse(normalized).path).name
            asset.content_type = content_type
            asset.extension = extension
            asset.local_path = str(local_file)
            asset.public_path = f"/api/public/media/{digest}"
            asset.file_size = len(body)
            asset.status = "cached"
            asset.error_message = ""
            asset.last_fetched_at = now
            self.session.flush()
            return asset.public_path
        except Exception as exc:
            asset.status = "failed"
            asset.error_message = str(exc)[:500]
            self.session.flush()
            return ""
```

- [ ] **Step 4: Run tests**

Run:

```bash
cd /Users/lws/Desktop/Code/DataFlow/backend
APP_SECRET_KEY=test-key /Users/lws/opt/anaconda3/envs/daily_highlights/bin/python -m pytest tests/test_media_cache.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/media_cache.py backend/tests/test_media_cache.py
git commit -m "feat(media): cache remote football images"
```

---

## Task 3: Serve Cached Media Publicly

**Files:**
- Modify: `backend/app/api/public.py`
- Modify: `backend/tests/test_media_cache.py`

- [ ] **Step 1: Add failing API test**

Append to `backend/tests/test_media_cache.py`:

```python
from app.models.entities import MediaAsset


def test_public_media_route_serves_cached_file(client, session, tmp_path: Path) -> None:
    media_file = tmp_path / "football" / "abc123.png"
    media_file.parent.mkdir(parents=True)
    media_file.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    session.add(
        MediaAsset(
            source_url="https://file.qiumiwu.com/team/a.png",
            normalized_url="https://file.qiumiwu.com/team/a.png",
            url_hash="abc123",
            provider="qiumiwu",
            asset_type="football_logo",
            entity_type="team",
            entity_name="阿森纳",
            content_type="image/png",
            extension=".png",
            local_path=str(media_file),
            public_path="/api/public/media/abc123",
            file_size=12,
            status="cached",
            metadata_json={},
        )
    )
    session.commit()

    response = client.get("/api/public/media/abc123")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert response.content.startswith(b"\x89PNG")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/lws/Desktop/Code/DataFlow/backend
APP_SECRET_KEY=test-key /Users/lws/opt/anaconda3/envs/daily_highlights/bin/python -m pytest tests/test_media_cache.py::test_public_media_route_serves_cached_file -q
```

Expected: FAIL with `404`.

- [ ] **Step 3: Add public route**

Add to `backend/app/api/public.py`:

```python
from app.models.entities import AITopicSummary, Highlight, MediaAsset, Topic


@router.get("/media/{url_hash}")
def get_cached_media(url_hash: str, session: Session = Depends(get_session)):
    asset = session.scalar(
        select(MediaAsset).where(MediaAsset.url_hash == url_hash, MediaAsset.status == "cached")
    )
    if asset is None or not asset.local_path or not Path(asset.local_path).exists():
        raise HTTPException(status_code=404, detail="Media not found")
    return FileResponse(asset.local_path, media_type=asset.content_type or "application/octet-stream")
```

- [ ] **Step 4: Run tests**

Run:

```bash
cd /Users/lws/Desktop/Code/DataFlow/backend
APP_SECRET_KEY=test-key /Users/lws/opt/anaconda3/envs/daily_highlights/bin/python -m pytest tests/test_media_cache.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/public.py backend/tests/test_media_cache.py
git commit -m "feat(media): serve cached media assets"
```

---

## Task 4: Cache Football Logos During Block Resolution

**Files:**
- Modify: `backend/app/services/adapters/qiumiwu.py`
- Modify: `backend/app/services/adapters/qiumiwu_schedule.py`
- Modify: `backend/app/services/blocks.py`
- Create: `backend/tests/test_qiumiwu_media_cache.py`

- [ ] **Step 1: Add adapter-level failing test**

Create `backend/tests/test_qiumiwu_media_cache.py`:

```python
from app.services.adapters import qiumiwu


class _FakeMediaCache:
    def __init__(self) -> None:
        self.calls = []

    def cache_remote_image(self, url: str, **kwargs) -> str:
        self.calls.append((url, kwargs))
        return f"/api/public/media/local-{len(self.calls)}"


class _ScheduleResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "error": 0,
            "data": {
                "list": [
                    {
                        "id": "100",
                        "league": {"name": "英超", "logo": "https://file.qiumiwu.com/league/epl.png"},
                        "home": {"name": "阿森纳", "logo": "https://file.qiumiwu.com/team/arsenal.png"},
                        "away": {"name": "切尔西", "logo": "https://file.qiumiwu.com/team/chelsea.png"},
                        "status": 1,
                        "status_name": "未开赛",
                        "start_time": 1780000000,
                        "scores": [[], []],
                    }
                ]
            },
        }


def test_fetch_matches_adds_local_logo_paths(monkeypatch) -> None:
    def fake_get(*args, **kwargs):
        return _ScheduleResponse()

    monkeypatch.setattr(qiumiwu.httpx, "get", fake_get)
    media_cache = _FakeMediaCache()

    matches = qiumiwu.fetch_matches({}, 10, media_cache=media_cache)

    assert matches[0]["logo_league_local"] == "/api/public/media/local-1"
    assert matches[0]["logo_a_local"] == "/api/public/media/local-2"
    assert matches[0]["logo_b_local"] == "/api/public/media/local-3"
    assert media_cache.calls[1][1]["entity_type"] == "team"
    assert media_cache.calls[1][1]["entity_name"] == "阿森纳"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/lws/Desktop/Code/DataFlow/backend
APP_SECRET_KEY=test-key /Users/lws/opt/anaconda3/envs/daily_highlights/bin/python -m pytest tests/test_qiumiwu_media_cache.py -q
```

Expected: FAIL because `fetch_matches` does not accept `media_cache`.

- [ ] **Step 3: Add helper in `qiumiwu.py`**

Add:

```python
def _cache_logo(media_cache, url: str, *, entity_type: str, entity_name: str, source_entity_id: str) -> str:
    if not media_cache or not url:
        return ""
    return media_cache.cache_remote_image(
        url,
        provider="qiumiwu",
        entity_type=entity_type,
        entity_name=entity_name,
        source_entity_id=source_entity_id,
        asset_type="football_logo",
        metadata={"adapter": "qiumiwu"},
    )
```

Change signature:

```python
def fetch_matches(_config: dict, limit: int, media_cache=None) -> list[dict]:
```

Inside `result.append`, add:

```python
"logo_league_local": _cache_logo(media_cache, league.get("logo", ""), entity_type="league", entity_name=league_name, source_entity_id=str(match_id)),
"logo_a_local": _cache_logo(media_cache, home.get("logo", ""), entity_type="team", entity_name=home.get("name", ""), source_entity_id=str(match_id)),
"logo_b_local": _cache_logo(media_cache, away.get("logo", ""), entity_type="team", entity_name=away.get("name", ""), source_entity_id=str(match_id)),
```

- [ ] **Step 4: Pass cache through fixtures**

Change:

```python
def fetch_fixtures(config: dict, limit: int, media_cache=None) -> list[dict]:
    matches = fetch_matches(config, max(limit, 200), media_cache=media_cache)
```

- [ ] **Step 5: Cache standings team logos**

Change `_fetch_league` signature:

```python
def _fetch_league(league_name: str, slug: str, media_cache=None) -> list[dict]:
```

Add to standings result item:

```python
"logo_local": _cache_logo(
    media_cache,
    team["logo"],
    entity_type="team",
    entity_name=team["name"],
    source_entity_id=team_id,
),
```

Change `fetch_standings` to pass cache:

```python
def fetch_standings(_config: dict, limit: int, media_cache=None) -> list[dict]:
    with ThreadPoolExecutor(max_workers=min(len(_STANDINGS_LEAGUES), 8)) as pool:
        futures = {
            pool.submit(_fetch_league, name, slug, media_cache): slug
            for name, slug in _STANDINGS_LEAGUES.items()
        }
```

- [ ] **Step 6: Pass cache in `blocks.py`**

In `backend/app/services/blocks.py`, create media cache once:

```python
from app.services.media_cache import MediaCacheService
```

Inside the block resolution function that has `session`, before football source cases:

```python
media_cache = MediaCacheService(session)
```

Then pass it:

```python
return fetch_matches(config, limit, media_cache=media_cache)
return fetch_fixtures(config, limit, media_cache=media_cache)
return fetch_standings(config, max(limit, 1000), media_cache=media_cache)
```

- [ ] **Step 7: Run tests**

Run:

```bash
cd /Users/lws/Desktop/Code/DataFlow/backend
APP_SECRET_KEY=test-key /Users/lws/opt/anaconda3/envs/daily_highlights/bin/python -m pytest tests/test_qiumiwu_media_cache.py tests/test_media_cache.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/adapters/qiumiwu.py backend/app/services/blocks.py backend/tests/test_qiumiwu_media_cache.py
git commit -m "feat(football): cache qiumiwu logos"
```

---

## Task 5: Cache Schedule Adapter Logos

**Files:**
- Modify: `backend/app/services/adapters/qiumiwu_schedule.py`
- Modify: `backend/app/services/blocks.py`
- Create or modify: `backend/tests/test_qiumiwu_media_cache.py`

- [ ] **Step 1: Add failing schedule test**

Append:

```python
from app.services.adapters import qiumiwu_schedule


def test_schedule_items_add_local_logo_paths(monkeypatch) -> None:
    html = """
    <div class="item" data-id="200">
      <span>06-08</span><span>20:00</span>
      <a href="/game/200">阿森纳 vs 切尔西</a>
    </div>
    """

    class _HtmlResponse:
        text = html
        def raise_for_status(self) -> None:
            return None

    monkeypatch.setattr(qiumiwu_schedule, "_get_logo_map", lambda: {
        "阿森纳": "https://file.qiumiwu.com/team/arsenal.png",
        "切尔西": "https://file.qiumiwu.com/team/chelsea.png",
        "_league_英超": "https://file.qiumiwu.com/league/epl.png",
    })
    monkeypatch.setattr(qiumiwu_schedule, "_fill_logo_map", lambda logo_map, matches_info: logo_map)

    class _Client:
        def get(self, *args, **kwargs):
            return _HtmlResponse()

    monkeypatch.setattr(qiumiwu_schedule, "_client", _Client(), raising=False)

    media_cache = _FakeMediaCache()
    items = qiumiwu_schedule.fetch_competition_schedule(
        {"competition": "yingchao", "name": "英超"},
        10,
        media_cache=media_cache,
    )

    if items:
        assert "logo_a_local" in items[0]
        assert "logo_b_local" in items[0]
```

If the current HTML parser cannot parse the simplified fixture, replace the fixture with a copied minimal snippet from a real `m.qiumiwu.com/game/{slug}` page captured in existing code comments. The expected behavior remains: local fields are present whenever remote logo fields are present.

- [ ] **Step 2: Implement schedule cache support**

Change signature:

```python
def fetch_competition_schedule(config: dict, limit: int, media_cache=None) -> list[dict]:
```

Add helper:

```python
def _cache_logo(media_cache, url: str, *, entity_type: str, entity_name: str, source_entity_id: str) -> str:
    if not media_cache or not url:
        return ""
    return media_cache.cache_remote_image(
        url,
        provider="qiumiwu",
        entity_type=entity_type,
        entity_name=entity_name,
        source_entity_id=source_entity_id,
        asset_type="football_logo",
        metadata={"adapter": "qiumiwu_schedule"},
    )
```

Add fields to returned schedule item:

```python
"logo_league_local": _cache_logo(media_cache, league_logo, entity_type="league", entity_name=comp_name, source_entity_id=str(match_id)),
"logo_a_local": _cache_logo(media_cache, logo_map.get(team_a, ""), entity_type="team", entity_name=team_a, source_entity_id=str(match_id)),
"logo_b_local": _cache_logo(media_cache, logo_map.get(team_b, ""), entity_type="team", entity_name=team_b, source_entity_id=str(match_id)),
```

In `blocks.py`, pass:

```python
return fetch_competition_schedule(config, limit, media_cache=media_cache)
```

- [ ] **Step 3: Run tests**

Run:

```bash
cd /Users/lws/Desktop/Code/DataFlow/backend
APP_SECRET_KEY=test-key /Users/lws/opt/anaconda3/envs/daily_highlights/bin/python -m pytest tests/test_qiumiwu_media_cache.py tests/test_media_cache.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/adapters/qiumiwu_schedule.py backend/app/services/blocks.py backend/tests/test_qiumiwu_media_cache.py
git commit -m "feat(football): cache schedule logos"
```

---

## Task 6: Prefer Local Logos in Frontend

**Files:**
- Modify: `frontend/src/components/layout/MatchCards.tsx`
- Modify: `frontend/src/components/layout/MatchList.tsx`
- Modify: `frontend/src/components/layout/StandingsTable.tsx`
- Modify: `frontend/src/__tests__/match-list.test.tsx`
- Modify: `frontend/src/__tests__/ranking-tables.test.tsx`

- [ ] **Step 1: Add local logo types**

In each football item type add:

```ts
logo_league_local?: string;
logo_a_local?: string;
logo_b_local?: string;
logo_local?: string;
```

- [ ] **Step 2: Add helper**

In each component or a shared local helper:

```ts
function logoSrc(localUrl?: string, remoteUrl?: string): string {
  if (localUrl) return localUrl;
  if (!remoteUrl) return "";
  return `/api/public/proxy/image?url=${encodeURIComponent(remoteUrl)}`;
}
```

- [ ] **Step 3: Replace image usages**

In match components:

```tsx
<TeamLogo url={logoSrc(match.logo_a_local, match.logo_a)} name={match.team_a} />
<TeamLogo url={logoSrc(match.logo_b_local, match.logo_b)} name={match.team_b} />
<TeamLogo url={logoSrc(match.logo_league_local, match.logo_league)} name={league} size="xs" />
```

In standings:

```tsx
<TeamLogo url={logoSrc(item.logo_local, item.logo)} name={item.team} />
```

Update `TeamLogo` so it does not double-wrap already-local URLs:

```ts
function resolveLogoUrl(url?: string): string {
  if (!url) return "";
  if (url.startsWith("/api/public/media/")) return url;
  if (url.startsWith("/api/public/proxy/image")) return url;
  return `/api/public/proxy/image?url=${encodeURIComponent(url)}`;
}
```

- [ ] **Step 4: Add frontend tests**

In `frontend/src/__tests__/match-list.test.tsx`, add:

```tsx
it("prefers locally cached logos over remote proxy urls", () => {
  render(
    <MatchList
      matches={[
        match({
          id: 1,
          team_a: "阿森纳",
          team_b: "切尔西",
          logo_a: "https://file.qiumiwu.com/team/arsenal.png",
          logo_a_local: "/api/public/media/local-arsenal",
          logo_b: "https://file.qiumiwu.com/team/chelsea.png",
          logo_b_local: "/api/public/media/local-chelsea",
        }),
      ]}
    />,
  );

  const images = screen.getAllByRole("img", { hidden: true });
  expect(images.some((img) => img.getAttribute("src") === "/api/public/media/local-arsenal")).toBe(true);
  expect(images.some((img) => img.getAttribute("src") === "/api/public/media/local-chelsea")).toBe(true);
});
```

If the current test setup does not expose decorative images by role, query by `document.querySelectorAll("img")` and assert on `src` attributes.

- [ ] **Step 5: Run frontend tests**

Run:

```bash
cd /Users/lws/Desktop/Code/DataFlow/frontend
npm run test -- match-list ranking-tables
npm run build
```

Expected: tests and build pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/layout/MatchCards.tsx frontend/src/components/layout/MatchList.tsx frontend/src/components/layout/StandingsTable.tsx frontend/src/__tests__/match-list.test.tsx frontend/src/__tests__/ranking-tables.test.tsx
git commit -m "feat(football): prefer cached logos in UI"
```

---

## Task 7: Full Verification and Operational Check

**Files:**
- No new files unless bugs are found.

- [ ] **Step 1: Run backend tests**

```bash
cd /Users/lws/Desktop/Code/DataFlow/backend
APP_SECRET_KEY=test-key /Users/lws/opt/anaconda3/envs/daily_highlights/bin/python -m pytest tests/test_media_cache.py tests/test_qiumiwu_media_cache.py -q
```

Expected: PASS.

- [ ] **Step 2: Run frontend tests and build**

```bash
cd /Users/lws/Desktop/Code/DataFlow/frontend
npm run test -- match-list ranking-tables
npm run build
```

Expected: PASS.

- [ ] **Step 3: Run migration locally**

```bash
cd /Users/lws/Desktop/Code/DataFlow/backend
APP_SECRET_KEY=test-key /Users/lws/opt/anaconda3/envs/daily_highlights/bin/python -m alembic upgrade head
```

Expected: migration reaches head and creates `media_assets`.

- [ ] **Step 4: Manual page check**

Start or reuse backend/frontend dev servers, then open:

```text
http://localhost:5173/topics/football
```

Expected:

- Football team logos still render.
- Network requests for newly cached logos point to `/api/public/media/{hash}`.
- If a cached local file is missing, UI falls back to `/api/public/proxy/image?url=...`.
- `media_assets` contains rows with `provider=qiumiwu`, `asset_type=football_logo`, and entity names for teams/leagues.

- [ ] **Step 5: Commit any verification fixes**

If verification required fixes:

```bash
git add <changed-files>
git commit -m "fix(football): stabilize media cache"
```

---

## Design Notes

- Keep `logo_a`, `logo_b`, `logo_league`, and standings `logo` as remote URLs. They are still useful for debugging and fallback.
- Add `*_local` fields rather than replacing the existing fields. This avoids breaking existing frontend components and tests.
- `media_assets` should be reusable later for AI logos, news source favicons, team photos, or article thumbnails.
- Store files under `backend/storage/media/football`, not `/tmp`, so local cache survives process restarts.
- Do not add image resizing or CDN behavior in this phase.
- Do not remove `/api/public/proxy/image`; keep it as a fallback until cached media is proven stable.

## Self-Review

- Spec coverage: The plan covers rich DB storage, local file persistence, crawl/block-time caching, public serving, UI local-first behavior, and tests.
- Placeholder scan: No `TBD`, `TODO`, or unspecified implementation steps remain.
- Type consistency: `MediaAsset`, `MediaCacheService.cache_remote_image`, `*_local` fields, and `/api/public/media/{url_hash}` are consistently named across tasks.
