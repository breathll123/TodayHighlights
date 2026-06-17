from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.entities import PageBlock, RawItem, Source, Topic
from app.services.blocks import get_page_blocks


def test_list_blocks_empty(client: TestClient) -> None:
    response = client.get("/api/admin/blocks")
    assert response.status_code == 200
    assert response.json() == []


def test_create_and_list_blocks(client: TestClient) -> None:
    payload = {
        "page_route": "/",
        "title": "今日热股",
        "source_type": "hot_stocks",
        "source_config": {"type": 10},
        "display_count": 5,
        "status": "published",
    }
    resp = client.post("/api/admin/blocks", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "今日热股"
    assert data["source_type"] == "hot_stocks"

    resp2 = client.get("/api/admin/blocks")
    assert len(resp2.json()) == 1


def test_update_block(client: TestClient) -> None:
    payload = {"page_route": "/", "title": "测试", "source_type": "topic", "source_config": {"topic_id": 1}, "status": "published"}
    resp = client.post("/api/admin/blocks", json=payload)
    block_id = resp.json()["id"]

    resp2 = client.put(f"/api/admin/blocks/{block_id}", json={"title": "已修改"})
    assert resp2.json()["title"] == "已修改"


def test_delete_block(client: TestClient) -> None:
    payload = {"page_route": "/", "title": "测试", "source_type": "topic", "source_config": {"topic_id": 1}, "status": "published"}
    resp = client.post("/api/admin/blocks", json=payload)
    block_id = resp.json()["id"]

    resp2 = client.delete(f"/api/admin/blocks/{block_id}")
    assert resp2.json()["deleted"] is True


def test_reorder_blocks(client: TestClient) -> None:
    for i in range(3):
        client.post("/api/admin/blocks", json={"page_route": "/", "title": f"Block{i}", "source_type": "topic", "source_config": {"topic_id": 1}, "sort_order": i, "status": "published"})

    resp = client.patch("/api/admin/blocks/reorder", json={"items": [{"id": 1, "sort_order": 2}, {"id": 2, "sort_order": 1}, {"id": 3, "sort_order": 0}]})
    assert resp.status_code == 200

    blocks = client.get("/api/admin/blocks").json()
    # blocks sorted by sort_order ascending: id=3(sort_order=0), id=2(sort_order=1), id=1(sort_order=2)
    assert blocks[0]["sort_order"] == 0
    assert blocks[1]["sort_order"] == 1
    assert blocks[2]["sort_order"] == 2


def test_public_page_blocks(client: TestClient) -> None:
    client.post("/api/admin/blocks", json={"page_route": "/", "title": "热股", "source_type": "hot_stocks", "source_config": {"type": 10}, "enabled": True, "status": "published"})
    client.post("/api/admin/blocks", json={"page_route": "/", "title": "隐藏", "source_type": "topic", "source_config": {"topic_id": 1}, "enabled": False, "status": "published"})

    resp = client.get("/api/public/pages/%2F/blocks")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["blocks"]) == 1
    assert data["blocks"][0]["title"] == "热股"


def test_page_blocks_include_block_data_updated_at() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as session:
        topic = Topic(name="股票", slug="stocks")
        source = Source(
            topic=topic,
            site="example",
            name="示例来源",
            entry_url="example://news",
            last_crawled_at=datetime(2026, 6, 17, 14, 5, 30),
        )
        session.add(source)
        session.flush()

        session.add(
            RawItem(
                source_id=source.id,
                external_id="item-1",
                url="https://example.com/item-1",
                title="测试内容",
                body="测试正文",
                published_at=datetime(2026, 6, 17, 13, 52, 18),
                content_hash="item-1",
            )
        )
        session.add(
            PageBlock(
                page_route="/topics/stocks",
                title="财经快讯",
                source_type="raw",
                source_config={"source_id": source.id},
                display_count=5,
                status="published",
            )
        )
        session.commit()

        blocks = get_page_blocks(session, "/topics/stocks")

    assert blocks[0]["data_updated_at"] == "2026-06-17T14:05:30"
