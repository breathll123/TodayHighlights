import json
from pathlib import Path

from app.sources.xueqiu import XueqiuAdapter


def test_parse_timeline_fixture() -> None:
    payload = json.loads((Path(__file__).parent / "fixtures/xueqiu_timeline.json").read_text())
    items = XueqiuAdapter.parse_timeline(payload)

    assert len(items) == 1
    item = items[0]
    assert item.external_id == "390032536"
    assert item.url == "https://xueqiu.com/7297620365/390032536"
    assert item.author == "投资者A"
    assert item.title == "新能源板块午后走强"
    assert item.body == "新能源板块午后走强，资金关注度明显提升。"
    assert item.metrics["like_count"] == 21
    assert item.metrics["view_count"] == 104282
    assert item.content_hash
