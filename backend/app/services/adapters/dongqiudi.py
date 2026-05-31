import httpx
from app.core.cache import ttl_cache

_headers = {
    "User-Agent": "Mozilla/5.0 DailyHighlights/0.1",
    "Accept": "application/json",
    "Referer": "https://www.dongqiudi.com/match",
}

# Leagues the user cares about
_PRIORITY_LEAGUES = {
    "欧冠", "英超", "西甲", "意甲", "德甲", "法甲", "中超", "世界杯", "世预赛",
    "欧联", "亚冠精英", "亚冠二级", "沙特联", "美职联", "中甲", "中乙", "足协杯",
    "国际友谊", "巴甲", "阿超", "荷甲", "葡超", "日职", "K联赛", "澳超",
    "欧洲杯", "美洲杯", "亚洲杯", "非洲杯",
}


@ttl_cache(30)
def fetch_matches(_config: dict, limit: int) -> list[dict]:
    """Fetch live match data from dongqiudi magicball API."""
    try:
        resp = httpx.get(
            "https://www.dongqiudi.com/magicball/v1/list/match_list",
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
        result = []
        for m in matches:
            comp = m.get("competition", {})
            league = comp.get("name", "")
            team_a = m.get("team_A", {})
            team_b = m.get("team_B", {})
            status = m.get("status", "")
            match_id = m.get("match_id", "")
            start_time = m.get("start_play", "")
            score_a = team_a.get("fs", "") or ""
            score_b = team_b.get("fs", "") or ""
            minute = m.get("minute_str", "") or m.get("minute", "")
            priority = 1 if league in _PRIORITY_LEAGUES else 0

            # Build title
            title = f"{team_a.get('name', '?')} vs {team_b.get('name', '?')}"

            # Build summary with status context
            if status == "Playing":
                summary = f"{league} · {minute}' · {team_a.get('name','?')} {score_a}-{score_b} {team_b.get('name','?')}"
            elif status == "Played":
                summary = f"{league} · 已结束 · {team_a.get('name','?')} {score_a}-{score_b} {team_b.get('name','?')}"
            elif status == "Fixture":
                time_str = start_time.split(" ")[-1][:5] if start_time else ""
                summary = f"{league} · {time_str} · {team_a.get('name','?')} vs {team_b.get('name','?')}"
            elif status in ("Postponed", "Cancelled", "Uncertain"):
                status_cn = {"Postponed": "延期", "Cancelled": "取消", "Uncertain": "待定"}.get(status, status)
                summary = f"{league} · {status_cn}"
            else:
                summary = f"{league}"

            result.append({
                "id": match_id,
                "title": title,
                "summary": summary,
                "url": f"https://www.dongqiudi.com/match/{match_id}",
                "league": league,
                "status": status,
                "team_a": team_a.get("name", ""),
                "team_b": team_b.get("name", ""),
                "score_a": score_a,
                "score_b": score_b,
                "minute": minute,
                "start_time": start_time,
                "priority": priority,
                "score": priority,
                "source_type": "dongqiudi_matches",
            })

        # Sort: priority leagues first, then by start_time
        result.sort(key=lambda x: (-x["priority"], x["start_time"]))
        return result[:limit]

    except Exception:
        return []
