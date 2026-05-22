from fastapi.testclient import TestClient


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
    }
    resp = client.post("/api/admin/blocks", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "今日热股"
    assert data["source_type"] == "hot_stocks"

    resp2 = client.get("/api/admin/blocks")
    assert len(resp2.json()) == 1


def test_update_block(client: TestClient) -> None:
    payload = {"page_route": "/", "title": "测试", "source_type": "topic", "source_config": {"topic_id": 1}}
    resp = client.post("/api/admin/blocks", json=payload)
    block_id = resp.json()["id"]

    resp2 = client.put(f"/api/admin/blocks/{block_id}", json={"title": "已修改"})
    assert resp2.json()["title"] == "已修改"


def test_delete_block(client: TestClient) -> None:
    payload = {"page_route": "/", "title": "测试", "source_type": "topic", "source_config": {"topic_id": 1}}
    resp = client.post("/api/admin/blocks", json=payload)
    block_id = resp.json()["id"]

    resp2 = client.delete(f"/api/admin/blocks/{block_id}")
    assert resp2.json()["deleted"] is True


def test_reorder_blocks(client: TestClient) -> None:
    for i in range(3):
        client.post("/api/admin/blocks", json={"page_route": "/", "title": f"Block{i}", "source_type": "topic", "source_config": {"topic_id": 1}, "sort_order": i})

    resp = client.patch("/api/admin/blocks/reorder", json={"items": [{"id": 1, "sort_order": 2}, {"id": 2, "sort_order": 1}, {"id": 3, "sort_order": 0}]})
    assert resp.status_code == 200

    blocks = client.get("/api/admin/blocks").json()
    # blocks sorted by sort_order ascending: id=3(sort_order=0), id=2(sort_order=1), id=1(sort_order=2)
    assert blocks[0]["sort_order"] == 0
    assert blocks[1]["sort_order"] == 1
    assert blocks[2]["sort_order"] == 2


def test_public_page_blocks(client: TestClient) -> None:
    client.post("/api/admin/blocks", json={"page_route": "/", "title": "热股", "source_type": "hot_stocks", "source_config": {"type": 10}, "enabled": True})
    client.post("/api/admin/blocks", json={"page_route": "/", "title": "隐藏", "source_type": "topic", "source_config": {"topic_id": 1}, "enabled": False})

    resp = client.get("/api/public/pages/%2F/blocks")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["blocks"]) == 1
    assert data["blocks"][0]["title"] == "热股"
