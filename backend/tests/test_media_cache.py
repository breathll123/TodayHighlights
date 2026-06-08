from datetime import datetime
from pathlib import Path

from sqlalchemy import inspect

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


def test_media_cache_downloads_once_and_reuses_asset(client, tmp_path: Path) -> None:
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
