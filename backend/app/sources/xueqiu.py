from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

import httpx

from app.sources.base import RawItemDraft


class XueqiuAdapter:
    base_url = "https://xueqiu.com"

    def fetch(self, entry_url: str, cookie: str) -> list[RawItemDraft]:
        headers = {
            "Cookie": cookie,
            "User-Agent": "Mozilla/5.0 DailyHighlights/0.1",
            "Accept": "application/json,text/plain,*/*",
        }
        with httpx.Client(timeout=15, follow_redirects=True, headers=headers) as client:
            response = client.get(entry_url)
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
            external_id = str(row.get("id", ""))
            target = str(row.get("target", ""))
            url = target if target.startswith("http") else f"{cls.base_url}{target}"
            author = str(row.get("user", {}).get("screen_name", ""))
            title = str(row.get("title") or "").strip()
            body = str(row.get("text") or "").strip()
            created_at_ms = row.get("created_at")
            published_at = None
            if isinstance(created_at_ms, int):
                published_at = datetime.fromtimestamp(created_at_ms / 1000, tz=timezone.utc).replace(tzinfo=None)
            metrics = {
                "reply_count": int(row.get("reply_count") or 0),
                "retweet_count": int(row.get("retweet_count") or 0),
                "fav_count": int(row.get("fav_count") or 0),
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
