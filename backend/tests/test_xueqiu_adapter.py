import json
from pathlib import Path

from app.sources import xueqiu
from app.sources.xueqiu import XueqiuAdapter, build_non_json_error, build_browser_headers, normalize_timeline_url


class _FakeResponse:
    def __init__(self, status_code: int, *, headers: dict[str, str], text: str, payload: dict | None = None):
        self.status_code = status_code
        self.headers = headers
        self.text = text
        self.content = text.encode()
        self._payload = payload or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict:
        return self._payload


class _FakeClient:
    urls: list[str] = []

    def __init__(self, *args, **kwargs):
        self.headers = kwargs.get("headers", {})
        self._responses = [
            _FakeResponse(200, headers={"content-type": "text/html; charset=utf-8"}, text="<html>login</html>"),
            _FakeResponse(200, headers={"content-type": "text/html; charset=utf-8"}, text="<html>home</html>"),
            _FakeResponse(
                200,
                headers={"content-type": "application/json; charset=utf-8"},
                text='{"list":[]}',
                payload={"list": []},
            ),
        ]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, url: str, **kwargs):
        self.urls.append(url)
        return self._responses.pop(0)


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


def test_build_browser_headers_uses_ajax_browser_headers() -> None:
    headers = build_browser_headers("xq_a_token=token")

    assert "Chrome/" in headers["User-Agent"]
    assert headers["X-Requested-With"] == "XMLHttpRequest"
    assert headers["Cookie"] == "xq_a_token=token"


def test_fetch_retries_after_html_response(monkeypatch) -> None:
    _FakeClient.urls = []
    monkeypatch.setattr(xueqiu.httpx, "Client", _FakeClient)

    items = XueqiuAdapter().fetch("https://xueqiu.com/v4/statuses/public_timeline_by_category.json", "cookie=1")

    assert items == []
    assert _FakeClient.urls == [
        "https://xueqiu.com/v4/statuses/public_timeline_by_category.json?category=-1&count=20&max_id=-1",
        "https://xueqiu.com",
        "https://xueqiu.com/v4/statuses/public_timeline_by_category.json?category=-1&count=20&max_id=-1",
    ]


def test_build_non_json_error_includes_safe_preview() -> None:
    message = build_non_json_error("text/html; charset=utf-8", "<html><title>登录</title></html>")

    assert "content_type=text/html; charset=utf-8" in message
    assert "登录" in message
