# -*- coding: utf-8 -*-
from fastapi.testclient import TestClient


def test_block_theme_defaults_and_persists(client: TestClient):
    """测试 PageBlock 通用 theme 属性在创建、修改及列表查询时的默认值与持久化逻辑"""
    # 1. 创建时缺省 theme → 默认为 "default"
    r = client.post("/api/admin/blocks", json={
        "page_route": "/topics/game", "title": "热门游戏",
        "source_type": "game_top_sellers", "source_config": {}, "status": "published",
    })
    assert r.status_code == 200
    block_id = r.json()["id"]
    assert r.json()["theme"] == "default"

    # 2. 将其更新为 arcade → 持久化保存并成功回显
    r2 = client.put(f"/api/admin/blocks/{block_id}", json={"theme": "arcade"})
    assert r2.json()["theme"] == "arcade"

    # 3. 后台列表拉取时，列表中应存在主题为 arcade 的实例
    r3 = client.get("/api/admin/blocks")
    assert any(b["theme"] == "arcade" for b in r3.json())
