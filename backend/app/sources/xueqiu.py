import json
from datetime import datetime
from hashlib import sha256
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx

from app.core.config import SH_TZ
from app.core.logging import observed_http_get
from app.core.logging_safety import response_preview
from app.sources.base import RawItemDraft


class XueqiuAdapter:
    base_url = "https://xueqiu.com"

    def fetch(self, entry_url: str, cookie: str) -> list[RawItemDraft]:
        request_url = normalize_timeline_url(entry_url)
        headers = build_browser_headers(cookie)
        with httpx.Client(timeout=15, follow_redirects=True, headers=headers) as client:
            response = fetch_timeline_response(client, request_url, attempt=1)
            if is_non_json_response(response):
                warm_up_session(client)
                response = fetch_timeline_response(client, request_url, attempt=2)

            if response.status_code in {400, 401, 403}:
                raise RuntimeError(f"Xueqiu request rejected with HTTP {response.status_code}")
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "json" not in content_type:
                raise RuntimeError(build_non_json_error(content_type, response.text))
            return self.parse_timeline(response.json())

    @classmethod
    def parse_timeline(cls, payload: dict[str, Any]) -> list[RawItemDraft]:
        rows = payload.get("list", [])
        drafts: list[RawItemDraft] = []
        for row in rows:
            raw_data = row.get("data", "")
            if isinstance(raw_data, str):
                try:
                    inner = json.loads(raw_data)
                except (json.JSONDecodeError, TypeError):
                    continue
            elif isinstance(raw_data, dict):
                inner = raw_data
            else:
                continue

            external_id = str(inner.get("id", row.get("id", "")))
            target = str(inner.get("target", ""))
            url = target if target.startswith("http") else f"{cls.base_url}{target}"
            author = str(inner.get("user", {}).get("screen_name", ""))
            title = str(inner.get("title") or "").strip()
            body = str(inner.get("description") or "").strip()
            created_at_ms = inner.get("created_at")
            published_at = None
            if isinstance(created_at_ms, int):
                published_at = datetime.fromtimestamp(created_at_ms / 1000, tz=SH_TZ).replace(tzinfo=None)
            metrics = {
                "reply_count": int(inner.get("reply_count") or 0),
                "retweet_count": int(inner.get("retweet_count") or 0),
                "like_count": int(inner.get("like_count") or 0),
                "view_count": int(inner.get("view_count") or 0),
            }
            digest = sha256(f"{external_id}|{url}|{title}|{body}".encode("utf-8")).hexdigest()
            drafts.append(
                RawItemDraft(
                    external_id=external_id,
                    url=url,
                    author=author,
                    title=title,
                    body=body,
                    published_at=published_at,
                    metrics=metrics,
                    content_hash=digest,
                )
            )
        return drafts


def normalize_timeline_url(entry_url: str) -> str:
    """Backfill required query params for Xueqiu's legacy public timeline endpoint."""
    parsed = urlparse(entry_url)
    if parsed.path != "/v4/statuses/public_timeline_by_category.json":
        return entry_url

    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.setdefault("category", "-1")
    query.setdefault("count", "20")
    query.setdefault("max_id", "-1")
    return urlunparse(parsed._replace(query=urlencode(query)))


def build_browser_headers(cookie: str) -> dict[str, str]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://xueqiu.com/",
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
    }
    if cookie:
        headers["Cookie"] = cookie
    return headers


def fetch_timeline_response(client: httpx.Client, request_url: str, *, attempt: int) -> httpx.Response:
    return observed_http_get(
        client.get,
        request_url,
        provider="xueqiu",
        operation="timeline",
        host="xueqiu.com",
        path=urlparse(request_url).path,
        attempt=attempt,
    )


def warm_up_session(client: httpx.Client) -> None:
    observed_http_get(
        client.get,
        XueqiuAdapter.base_url,
        provider="xueqiu",
        operation="warmup",
        host="xueqiu.com",
        path="/",
    )


def is_non_json_response(response: httpx.Response) -> bool:
    return response.status_code == 200 and "json" not in response.headers.get("content-type", "")


def build_non_json_error(content_type: str, text: str) -> str:
    preview = response_preview(text, max_chars=180)
    return (
        "Xueqiu response is not JSON; Cookie may be expired or page structure changed "
        f"(content_type={content_type or '-'}, preview={preview or '-'})"
    )
