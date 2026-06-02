import re
from datetime import datetime
from hashlib import sha256

import httpx

from app.core.config import SH_TZ
from app.sources.base import RawItemDraft

_headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html",
}

_COMPANIES = [
    "Anthropic", "OpenAI", "Google Deep Mind", "Facebook AI研究实验室",
    "Moonshot AI", "阿里巴巴", "智谱AI", "DeepSeek-AI", "xAI",
    "Meta", "Microsoft", "Mistral AI", "Cohere", "AI21 Labs",
    "01.AI", "百川智能", "字节跳动", "腾讯", "百度",
    "Apple", "Amazon", "NVIDIA", "Intel", "AMD",
]


class DatalearnerAdapter:

    def fetch(self, entry_url: str, cookie: str) -> list[RawItemDraft]:
        subtype = entry_url.replace("datalearner://", "") if entry_url.startswith("datalearner://") else ""
        handler = {
            "leaderboard": self._fetch_leaderboard,
        }.get(subtype)
        if handler is None:
            return []
        return handler(subtype)

    def _fetch_leaderboard(self, subtype: str) -> list[RawItemDraft]:
        resp = httpx.get(
            "https://www.datalearner.com/leaderboards",
            headers=_headers,
            timeout=30,
            follow_redirects=True,
        )
        resp.raise_for_status()
        html = resp.text

        table_m = re.search(r"<table[^>]*>(.*?)</table>", html, re.DOTALL)
        if not table_m:
            return []

        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_m.group(1), re.DOTALL)
        header_cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", rows[0], re.DOTALL)
        headers = [re.sub(r"<[^>]+>", "", c).strip() for c in header_cells]
        benchmark_names = [h for h in headers[3:-2] if h]

        drafts = []
        rank = 0
        for row in rows[1:]:
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
            values = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
            values = [re.sub(r"\s+", " ", v).strip() for v in values]

            if len(values) < 5 or not values[2]:
                continue

            rank_str = values[1] if len(values) > 1 else ""
            if rank_str and rank_str.isdigit():
                rank = int(rank_str)
            elif not rank_str:
                rank += 1

            model_company = values[2]
            company = ""
            model_name = model_company
            for c in _COMPANIES:
                if model_company.endswith(c):
                    model_name = model_company[: -len(c)]
                    company = c
                    break

            scores = {}
            for i, bname in enumerate(benchmark_names):
                idx = 3 + i
                if idx < len(values):
                    scores[bname] = values[idx].replace("—", "").strip()

            body = " · ".join(f"{k}: {v}" for k, v in scores.items() if v)
            content_str = f"dl|{rank}|{model_name}|{company}|{body}"

            drafts.append(RawItemDraft(
                external_id=f"dl_{model_name}",
                url="https://www.datalearner.com/leaderboards",
                author=company,
                title=model_name,
                body=body,
                published_at=datetime.now(SH_TZ).replace(tzinfo=None),
                metrics={
                    "rank": rank,
                    "model": model_name,
                    "company": company,
                    "license": values[8] if len(values) > 8 else "",
                    **scores,
                },
                content_hash=sha256(content_str.encode()).hexdigest(),
            ))

        return drafts
