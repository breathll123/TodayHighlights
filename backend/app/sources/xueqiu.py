import json
from datetime import datetime
from hashlib import sha256
from typing import Any

import httpx

from app.core.config import SH_TZ
from app.core.logging import observed_http_get
from app.sources.base import RawItemDraft


class XueqiuAdapter:
    base_url = "https://xueqiu.com"

    def fetch(self, entry_url: str, cookie: str) -> list[RawItemDraft]:
        headers = {
            "Cookie": cookie,
            "User-Agent": "Mozilla/5.0 TodayHighlights/0.1",
            "Accept": "application/json,text/plain,*/*",
        }
        with httpx.Client(timeout=15, follow_redirects=True, headers=headers) as client:
            response = observed_http_get(
                client.get,
                entry_url,
                provider="xueqiu",
                operation="timeline",
                host="xueqiu.com",
                path="/statuses/user_timeline.json",
            )
            if response.status_code in {401, 403}:
                raise RuntimeError(f"Xueqiu request rejected with HTTP {response.status_code}")
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "json" not in content_type:
                raise RuntimeError("Xueqiu response is not JSON; Cookie may be expired or page structure changed")
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
