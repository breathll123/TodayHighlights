from datetime import datetime

from sqlalchemy import inspect

from app.core.database import get_session
from app.models.entities import MediaAsset


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
