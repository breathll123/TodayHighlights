from datetime import datetime
from hashlib import sha256

import httpx

from app.core.config import SH_TZ
from app.core.logging import observed_http_get
from app.sources.base import RawItemDraft


class TonghuashunAdapter:

    def fetch(self, entry_url: str, cookie: str) -> list[RawItemDraft]:
        try:
            resp = observed_http_get(
                httpx.get,
                "https://news.10jqka.com.cn/tapp/news/push/stock?page=1",
                provider="tonghuashun",
                operation="stock_news",
                host="news.10jqka.com.cn",
                path="/tapp/news/push/stock",
                headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"},
                timeout=15,
            )
            resp.raise_for_status()
            items = resp.json().get("data", {}).get("list", [])
            drafts = []
            for item in items:
                news_id = str(item.get("id", ""))
                title = item.get("title", "")
                digest = item.get("digest", "")
                url = item.get("url", "")
                ctime = item.get("ctime", "")
                content_str = f"{news_id}|{url}|{title}"
                pub_time = None
                if ctime and ctime.isdigit():
                    pub_time = datetime.fromtimestamp(int(ctime), tz=SH_TZ).replace(tzinfo=None)
                drafts.append(RawItemDraft(
                    external_id=f"ths_news_{news_id}",
                    url=url,
                    author="",
                    title=title,
                    body=digest,
                    published_at=pub_time,
                    metrics={"source": "tonghuashun", "news_id": news_id},
                    content_hash=sha256(content_str.encode()).hexdigest(),
                ))
            return drafts
        except Exception:
            raise
