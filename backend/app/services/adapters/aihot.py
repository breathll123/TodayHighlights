import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

import httpx

from app.core.cache import ttl_cache
from app.core.logging import log_adapter_failure, observed_http_get

_CST = timezone(timedelta(hours=8))
_headers = {"User-Agent": "Mozilla/5.0 TodayHighlights/0.1", "Accept": "application/xml"}


def _parse_feed(xml_text: str) -> list[dict]:
    """Parse RSS XML into article dicts."""
    root = ET.fromstring(xml_text)
    items = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = (item.findtext("description") or "").strip()
        pub_str = (item.findtext("pubDate") or "").strip()
        author = (item.findtext("author") or "").strip()

        # Parse date
        pub_date = None
        try:
            pub_date = datetime.strptime(pub_str, "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=timezone.utc)
        except ValueError:
            pass

        # Extract source name from author field: "noreply@aihot.virxact.com (X：小互 (@xiaohu))"
        source = ""
        if author:
            m = re.search(r"\((.+?)\)", author)
            if m:
                source = m.group(1)
            else:
                source = author

        # Clean description — remove HTML
        desc_clean = re.sub(r"<[^>]+>", "", desc)

        items.append({
            "title": title,
            "url": link,
            "description": desc_clean,
            "source": source,
            "published_at": pub_date.isoformat() if pub_date else "",
        })
    return items


@ttl_cache(300)
def fetch_news(_config: dict, limit: int) -> list[dict]:
    """Fetch AI news from AI HOT RSS feed."""
    try:
        try:
            resp = observed_http_get(
                httpx.get,
                "https://aihot.virxact.com/feed.xml",
                provider="aihot", operation="news_feed",
                host="aihot.virxact.com", path="/feed.xml",
                headers=_headers,
                timeout=20,
                follow_redirects=True,
            )
            # 如果响应状态码是 304 (未修改)，直接静默返回空列表，避免后续空文本解析报错
            if resp.status_code == 304:
                return []
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            # 捕获部分 httpx 版本将 304 当作重定向异常抛出的情况，返回空列表实现静默降级
            if "304" in str(exc) or "Not Modified" in str(exc):
                return []
            raise

        articles = _parse_feed(resp.text)
        result = []
        for i, a in enumerate(articles[:limit]):
            result.append({
                "id": f"aihot_{i}",
                "title": a["title"],
                "summary": a["description"],
                "url": a["url"],
                "source": a["source"],
                "published_at": a["published_at"],
                "score": 0,
                "source_type": "aihot_news",
            })
        if not result:
            raise ValueError("empty RSS — don't cache")
        return result
    except Exception as exc:
        # 对于其它未知解析异常或 4xx/5xx 请求错误，照常记录适配器失败事件
        log_adapter_failure(provider="aihot", operation="news_feed", stage="parse", exc=exc)
        return []
