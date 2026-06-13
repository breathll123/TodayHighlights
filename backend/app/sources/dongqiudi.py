import json
from datetime import datetime
from hashlib import sha256

import httpx

from app.core.config import SH_TZ
from app.core.logging import observed_http_get
from app.sources.base import RawItemDraft

_headers = {
    "User-Agent": "Mozilla/5.0 TodayHighlights/0.1",
    "Accept": "application/json",
    "Referer": "https://www.dongqiudi.com/match",
}

# Leagues the user cares about — prioritize these in display
_PRIORITY_LEAGUES = {
    "欧冠", "英超", "西甲", "意甲", "德甲", "法甲", "中超", "世界杯", "世预赛",
    "欧联", "亚冠精英", "亚冠二级", "沙特联", "美职联", "中甲", "中乙", "足协杯",
    "国际友谊", "巴甲", "阿超", "荷甲", "葡超", "日职", "K联赛", "澳超",
    "欧洲杯", "美洲杯", "亚洲杯", "非洲杯",
}


class DongqiudiAdapter:

    def fetch(self, entry_url: str, cookie: str) -> list[RawItemDraft]:
        subtype = entry_url.replace("dongqiudi://", "") if entry_url.startswith("dongqiudi://") else ""
        handler = {
            "matches": self._fetch_matches,
        }.get(subtype)
        if handler is None:
            return []
        return handler(subtype)

    def _fetch_matches(self, subtype: str) -> list[RawItemDraft]:
        """Fetch match data from magicball API. Returns all matches grouped by league."""
        resp = observed_http_get(
            httpx.get,
            "https://www.dongqiudi.com/magicball/v1/list/match_list",
            provider="dongqiudi",
            operation="match_list",
            host="www.dongqiudi.com",
            path="/magicball/v1/list/match_list",
            params={"language": "zh-CN", "cmp_type": "soccer", "tab_type": "all"},
            headers=_headers,
            timeout=20,
            follow_redirects=True,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            return []

        matches = data.get("data", {}).get("matches", []) or []
        drafts = []
        for m in matches:
            comp = m.get("competition", {})
            league = comp.get("name", "")
            team_a = m.get("team_A", {})
            team_b = m.get("team_B", {})
            status = m.get("status", "")
            match_id = m.get("match_id", "")
            start_time = m.get("start_play", "")

            # Parse match time
            published_at = None
            if start_time:
                try:
                    published_at = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S").replace(tzinfo=SH_TZ)
                except ValueError:
                    published_at = None

            # Build title: "曼联 vs 利物浦"
            title = f"{team_a.get('name', '?')} vs {team_b.get('name', '?')}"

            # Build body with status-aware info
            score_a = team_a.get("fs", "") or "—"
            score_b = team_b.get("fs", "") or "—"
            minute = m.get("minute_str", "") or m.get("minute", "")
            period = m.get("period", "")

            if status == "Playing":
                body = f"{league} · {minute}' · {team_a.get('name','?')} {score_a}-{score_b} {team_b.get('name','?')}"
            elif status == "Played":
                body = f"{league} · 已结束 · {team_a.get('name','?')} {score_a}-{score_b} {team_b.get('name','?')}"
            elif status == "Fixture":
                time_str = start_time.split(" ")[-1][:5] if start_time else ""
                body = f"{league} · {time_str} · {team_a.get('name','?')} vs {team_b.get('name','?')}"
            elif status in ("Postponed", "Cancelled", "Uncertain"):
                status_cn = {"Postponed": "延期", "Cancelled": "取消", "Uncertain": "待定"}.get(status, status)
                body = f"{league} · {status_cn}"
            else:
                body = f"{league}"

            score_str = f"{score_a}-{score_b}" if score_a != "—" or score_b != "—" else ""
            content_str = f"dqd|{match_id}|{status}|{score_str}|{start_time}"
            priority = 1 if league in _PRIORITY_LEAGUES else 0

            drafts.append(RawItemDraft(
                external_id=f"dqd_{match_id}",
                url=f"https://www.dongqiudi.com/match/{match_id}",
                author=league,
                title=title,
                body=body,
                published_at=published_at,
                metrics={
                    "league": league,
                    "status": status,
                    "team_a": team_a.get("name", ""),
                    "team_b": team_b.get("name", ""),
                    "score_a": score_a,
                    "score_b": score_b,
                    "minute": minute,
                    "period": period,
                    "start_time": start_time,
                    "priority": priority,
                    "logo_a": team_a.get("logo", ""),
                    "logo_b": team_b.get("logo", ""),
                },
                content_hash=sha256(content_str.encode()).hexdigest(),
            ))

        return drafts
