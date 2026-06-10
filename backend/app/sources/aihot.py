import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from hashlib import sha256

import httpx

from app.core.config import SH_TZ
from app.sources.base import RawItemDraft

_headers = {"User-Agent": "Mozilla/5.0 TodayHighlights/0.1", "Accept": "application/xml"}


class AihotAdapter:

    def fetch(self, entry_url: str, cookie: str) -> list[RawItemDraft]:
        subtype = entry_url.replace("aihot://", "") if entry_url.startswith("aihot://") else ""
        handler = {
            "news": self._fetch_news,
        }.get(subtype)
        if handler is None:
            return []
        return handler(subtype)

    def _fetch_news(self, subtype: str) -> list[RawItemDraft]:
        resp = httpx.get(
            "https://aihot.virxact.com/feed.xml",
            headers=_headers,
            timeout=20,
            follow_redirects=True,
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        drafts = []

        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            desc = (item.findtext("description") or "").strip()
            pub_str = (item.findtext("pubDate") or "").strip()
            author = (item.findtext("author") or "").strip()

            pub_date = None
            try:
                pub_date = datetime.strptime(pub_str, "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=timezone.utc)
            except ValueError:
                pub_date = datetime.now(SH_TZ).replace(tzinfo=None)

            # Extract source name
            source = ""
            if author:
                m = re.search(r"\((.+?)\)", author)
                if m:
                    source = m.group(1)
                else:
                    source = author

            desc_clean = re.sub(r"<[^>]+>", "", desc)
            content_str = f"aihot|{title}|{link}"

            drafts.append(RawItemDraft(
                external_id=f"aihot_{sha256(link.encode()).hexdigest()[:16]}",
                url=link,
                author=source,
                title=title,
                body=desc_clean,
                published_at=pub_date,
                metrics={"source": source},
                content_hash=sha256(content_str.encode()).hexdigest(),
            ))

        return drafts
