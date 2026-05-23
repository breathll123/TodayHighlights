from fastapi.testclient import TestClient


def test_publish_page(client: TestClient) -> None:
    client.post("/api/admin/blocks", json={
        "page_route": "/", "title": "方块1", "source_type": "topic",
        "source_config": {"topic_id": 1}, "block_key": "key-1",
        "col_span": 2, "status": "draft",
    })
    client.post("/api/admin/blocks", json={
        "page_route": "/", "title": "方块2", "source_type": "hot_stocks",
        "source_config": {"type": 10}, "block_key": "key-2",
        "col_span": 1, "status": "draft",
    })

    resp = client.post("/api/admin/pages/%2F/publish")
    assert resp.status_code == 200
    assert resp.json() == {"published": True, "blocks": 2}

    resp2 = client.get("/api/public/pages/%2F/blocks")
    assert len(resp2.json()["blocks"]) == 2


def test_publish_removes_deleted_blocks(client: TestClient) -> None:
    client.post("/api/admin/blocks", json={
        "page_route": "/", "title": "旧方块", "source_type": "topic",
        "source_config": {"topic_id": 1}, "block_key": "old-key", "status": "draft",
    })
    client.post("/api/admin/pages/%2F/publish")
    assert len(client.get("/api/public/pages/%2F/blocks").json()["blocks"]) == 1

    blocks = client.get("/api/admin/blocks").json()
    client.delete(f"/api/admin/blocks/{blocks[0]['id']}")

    client.post("/api/admin/pages/%2F/publish")
    assert len(client.get("/api/public/pages/%2F/blocks").json()["blocks"]) == 0
