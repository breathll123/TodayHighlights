import httpx
from app.core.cache import ttl_cache

_headers = {
    "User-Agent": "Mozilla/5.0 DailyHighlights/0.1",
    "Accept": "application/json",
    "Referer": "https://www.qiumiwu.com/",
}

_STATUS_NAMES: dict[int, str] = {
    1: "未开赛",
    2: "上半场",
    8: "下半场",
    15: "完场",
    18: "延期",
    19: "取消",
}

# Leagues the user cares about — prioritized in display
_PRIORITY_LEAGUES = {
    "欧冠杯", "英超", "西甲", "意甲", "德甲", "法甲", "中超", "世界杯",
    "欧联杯", "亚冠杯", "沙特联", "美职联", "中甲", "中乙", "足协杯",
    "国际赛", "巴甲", "阿超", "荷甲", "葡超", "日职联", "韩K联", "澳超",
    "欧洲杯", "美洲杯", "亚洲杯", "非洲杯", "世预赛",
    "瑞典超", "挪超", "芬超", "瑞士超", "比甲", "土超", "俄超",
    "英冠", "西乙", "德乙", "意乙", "法乙", "日职乙",
}


@ttl_cache(30)
def fetch_matches(_config: dict, limit: int) -> list[dict]:
    """Fetch live match data from qiumiwu schedule API."""
    try:
        resp = httpx.get(
            "https://api.qiumiwu.com/v5/game/schedule/0/1/0/0/0",
            params={"reqfrom": "web"},
            headers=_headers,
            timeout=20,
            follow_redirects=True,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("error") != 0:
            return []

        matches = data.get("data", {}).get("list", []) or []
        result = []
        for m in matches:
            league = m.get("league", {})
            league_name = league.get("name", "")
            home = m.get("home", {})
            away = m.get("away", {})
            status = m.get("status", 0)
            status_name = _STATUS_NAMES.get(status, m.get("status_name", "未知"))
            match_id = m.get("id", "")
            start_ts = m.get("start_time", 0)
            scores = m.get("scores", [])
            priority = 1 if league_name in _PRIORITY_LEAGUES else 0

            # Parse scores array: [home_ft, away_ft, home_ht, away_ht, ?, ?, home_corner, away_corner, ?]
            home_score = str(scores[0][0]) if scores and scores[0] else ""
            away_score = str(scores[0][1]) if scores and scores[0] else ""
            home_ht = str(scores[0][2]) if scores and len(scores[0]) > 2 else ""
            away_ht = str(scores[0][3]) if scores and len(scores[0]) > 3 else ""

            title = f"{home.get('name', '?')} vs {away.get('name', '?')}"

            # Build summary
            import datetime as _dt
            time_str = _dt.datetime.fromtimestamp(start_ts).strftime("%H:%M") if start_ts else ""

            if status in (2, 8):  # Playing
                summary = f"{league_name} · {status_name} · {home.get('name','?')} {home_score}-{away_score} {away.get('name','?')}"
            elif status == 15:  # Played
                summary = f"{league_name} · 已结束 · {home.get('name','?')} {home_score}-{away_score} {away.get('name','?')}"
            elif status == 1:  # Fixture
                summary = f"{league_name} · {time_str} · {home.get('name','?')} vs {away.get('name','?')}"
            else:
                summary = f"{league_name} · {status_name}"

            # Append note if available (extra time, penalties, etc.)
            note = m.get("note", "")
            if note:
                summary += f"  ({note})"

            result.append({
                "id": match_id,
                "title": title,
                "summary": summary,
                "url": f"https://www.qiumiwu.com/game/{match_id}",
                "league": league_name,
                "status": status,
                "status_name": status_name,
                "team_a": home.get("name", ""),
                "team_b": away.get("name", ""),
                "score_a": home_score,
                "score_b": away_score,
                "score_ht_a": home_ht,
                "score_ht_b": away_ht,
                "start_time": _dt.datetime.fromtimestamp(start_ts).isoformat() if start_ts else "",
                "note": note,
                "stage": m.get("stage", ""),
                "priority": priority,
                "score": priority,
                "source_type": "qiumiwu_matches",
            })

        result.sort(key=lambda x: (-x["priority"], x["start_time"]))
        return result[:limit]

    except Exception:
        return []
