import json
from pathlib import Path

from app.sources.xueqiu import XueqiuAdapter, build_non_json_error, normalize_timeline_url


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


def test_normalize_timeline_url_adds_required_defaults() -> None:
    url = normalize_timeline_url("https://xueqiu.com/v4/statuses/public_timeline_by_category.json")

    assert url == (
        "https://xueqiu.com/v4/statuses/public_timeline_by_category.json"
        "?category=-1&count=20&max_id=-1"
    )


def test_normalize_timeline_url_keeps_custom_params() -> None:
    url = normalize_timeline_url(
        "https://xueqiu.com/v4/statuses/public_timeline_by_category.json?category=6&count=10"
    )

    assert url == (
        "https://xueqiu.com/v4/statuses/public_timeline_by_category.json"
        "?category=6&count=10&max_id=-1"
    )


def test_build_non_json_error_includes_safe_preview() -> None:
    message = build_non_json_error("text/html; charset=utf-8", "<html><title>登录</title></html>")

    assert "content_type=text/html; charset=utf-8" in message
    assert "登录" in message
