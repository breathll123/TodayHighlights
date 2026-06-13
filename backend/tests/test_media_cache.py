import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as SASession

from app.core.database import get_session
from app.models.entities import MediaAsset
from app.services.media_cache import MediaCacheService, is_safe_remote_url, url_hash


def test_media_assets_table_has_rich_metadata_columns(client) -> None:
    session = next(client.app.dependency_overrides[get_session]())
    columns = {col["name"] for col in inspect(session.bind).get_columns("media_assets")}

    assert {
        "id", "source_url", "normalized_url", "url_hash", "provider",
        "asset_type", "entity_type", "entity_name", "source_entity_id",
        "original_filename", "content_type", "extension", "local_path",
        "public_path", "file_size", "width", "height", "status",
        "fetch_count", "last_fetched_at", "last_used_at", "error_message",
        "metadata_json", "created_at", "updated_at",
    }.issubset(columns)


def test_media_asset_model_can_store_metadata(client) -> None:
    session = next(client.app.dependency_overrides[get_session]())
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


def test_is_safe_remote_url_blocks_internal_hosts() -> None:
    assert is_safe_remote_url("https://file.qiumiwu.com/team/a.png") is True
    assert is_safe_remote_url("http://127.0.0.1/a.png") is False
    assert is_safe_remote_url("http://localhost/a.png") is False
    assert is_safe_remote_url("http://192.168.1.2/a.png") is False


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


def test_media_cache_downloads_once_and_reuses_asset(client, tmp_path: Path, caplog) -> None:
    caplog.set_level(logging.INFO)
    session = next(client.app.dependency_overrides[get_session]())
    fake_client = _FakeClient()
    service = MediaCacheService(session, storage_root=tmp_path, http_client=fake_client)

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
    assert fake_client.calls == 1
    asset_hash = url_hash("https://file.qiumiwu.com/team/a.png")
    assert (tmp_path / "football" / f"{asset_hash}.png").exists()
    events = [getattr(record, "event", "") for record in caplog.records]
    assert "media_download_finished" in events
    assert "media_cache_hit" in events
    rendered = " ".join(str(getattr(record, "event_fields", {})) for record in caplog.records)
    assert "https://file.qiumiwu.com/team/a.png" not in rendered


def test_public_media_route_serves_cached_file(client, tmp_path: Path) -> None:
    session = next(client.app.dependency_overrides[get_session]())
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


def test_media_cache_removes_file_when_commit_fails(client, tmp_path: Path, monkeypatch, caplog) -> None:
    caplog.set_level(logging.INFO)
    session = next(client.app.dependency_overrides[get_session]())
    service = MediaCacheService(session, storage_root=tmp_path, http_client=_FakeClient())

    def fail_commit(self):
        raise RuntimeError("commit failed")

    monkeypatch.setattr(SASession, "commit", fail_commit)

    result = service.cache_remote_image(
        "https://file.qiumiwu.com/team/cleanup.png",
        provider="qiumiwu",
        entity_type="team",
        entity_name="清理测试",
        source_entity_id="match_cleanup",
    )

    assert result == ""
    assert not list(tmp_path.rglob("*.png"))
    record = next(
        record
        for record in caplog.records
        if getattr(record, "event", "") == "media_cache_failed"
    )
    assert record.event_fields["exception_type"] == "RuntimeError"
    assert "cleanup.png" not in str(record.event_fields)


def test_media_cache_returns_existing_asset_after_unique_race(client, tmp_path: Path, monkeypatch) -> None:
    session = next(client.app.dependency_overrides[get_session]())
    service = MediaCacheService(session, storage_root=tmp_path, http_client=_FakeClient())
    source_url = "https://file.qiumiwu.com/team/race.png"
    digest = url_hash(source_url)
    existing_file = tmp_path / "football" / f"{digest}.png"
    existing_file.parent.mkdir(parents=True)
    existing_file.write_bytes(b"\x89PNG\r\n\x1a\nwinner")
    original_commit = SASession.commit
    original_rollback = SASession.rollback
    raised = False
    inserted = False

    def race_commit(self):
        nonlocal raised
        if raised:
            return original_commit(self)
        raised = True
        raise IntegrityError("insert media asset", {}, Exception("unique constraint"))

    def rollback_then_insert_winner(self):
        nonlocal inserted
        original_rollback(self)
        if inserted:
            return None
        inserted = True
        competing = SASession(bind=self.get_bind())
        try:
            competing.add(
                MediaAsset(
                    source_url=source_url,
                    normalized_url=source_url,
                    url_hash=digest,
                    provider="qiumiwu",
                    asset_type="football_logo",
                    entity_type="team",
                    entity_name="竞态测试",
                    content_type="image/png",
                    extension=".png",
                    local_path=str(existing_file),
                    public_path=f"/api/public/media/{digest}",
                    file_size=existing_file.stat().st_size,
                    status="cached",
                    metadata_json={},
                )
            )
            original_commit(competing)
        finally:
            competing.close()
        return None

    monkeypatch.setattr(SASession, "commit", race_commit)
    monkeypatch.setattr(SASession, "rollback", rollback_then_insert_winner)

    result = service.cache_remote_image(
        source_url,
        provider="qiumiwu",
        entity_type="team",
        entity_name="竞态测试",
        source_entity_id="match_race",
    )

    assert result == f"/api/public/media/{digest}"
