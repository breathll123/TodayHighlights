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
                "logo_league": league.get("logo", ""),
                "status": status,
                "status_name": status_name,
                "team_a": home.get("name", ""),
                "team_b": away.get("name", ""),
                "logo_a": home.get("logo", ""),
                "logo_b": away.get("logo", ""),
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


# League slug mapping for standings
_STANDINGS_LEAGUES = {
    "英超": "yingchao", "西甲": "xijia", "意甲": "yijia", "德甲": "dejia",
    "法甲": "fajia", "中超": "zhongchao", "欧冠": "ouguanbei",
}

_STANDINGS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
}


@ttl_cache(300)
def fetch_standings(_config: dict, limit: int) -> list[dict]:
    """Fetch league standings from qiumiwu mobile pages."""
    import re

    result = []
    for league_name, slug in _STANDINGS_LEAGUES.items():
        try:
            resp = httpx.get(
                f"https://m.qiumiwu.com/league/{slug}/standings",
                headers=_STANDINGS_HEADERS,
                timeout=20,
            )
            resp.raise_for_status()
            html = resp.text

            # Season
            year_m = re.search(r"(\d{4}-\d{4})", html)
            season = year_m.group(1) if year_m else ""

            # Update time
            update_m = re.search(r"(\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{1,2})更新", html)
            update_time = update_m.group(1) if update_m else ""

            # Basic table — first 20 teams
            teams = []
            seen = set()
            for m in re.finditer(
                r'<a class="stats__table__list"\s+href="([^"]*)"(?:\s+pos="(\d+)")?[^>]*>\s*'
                r"<span>(\d+)</span>\s*"
                r'<img\s+alt="([^"]*)"\s+src="([^"]*)"[^>]*>\s*'
                r"<span>([^<]*)</span>",
                html,
            ):
                rank = int(m.group(3))
                if rank <= 20 and rank not in seen:
                    seen.add(rank)
                    teams.append({
                        "rank": rank,
                        "name": m.group(6),
                        "logo": m.group(5),
                    })
            teams.sort(key=lambda x: x["rank"])

            # Stats — per-team rows in type="info" section
            info_start = html.find('type="info"')
            if info_start < 0:
                continue

            info_html = html[info_start:]
            stat_rows = re.findall(
                r'<div class="stats__table__list">((?:\s*<span[^>]*>[^<]*</span>\s*)+)</div>',
                info_html,
            )

            stats_list = []
            for row_html in stat_rows:
                values = re.findall(r"<span[^>]*>\s*([0-9./\-]+[%]?)\s*</span>", row_html)
                if len(values) == 10 and values[0].strip().isdigit():
                    stats_list.append({
                        "gp": values[0].strip(),
                        "pts": values[1].strip(),
                        "wdl": values[2].strip(),
                        "gf": values[3].strip(),
                        "ga": values[4].strip(),
                        "gd": values[5].strip(),
                        "avg_gf": values[6].strip(),
                        "avg_ga": values[7].strip(),
                        "avg_gd": values[8].strip(),
                        "win_rate": values[9].strip(),
                    })

            # Match teams with stats (first 20 for 总榜)
            for i, team in enumerate(teams):
                if i < len(stats_list):
                    s = stats_list[i]
                    team["gp"] = s["gp"]
                    team["pts"] = s["pts"]
                    team["wdl"] = s["wdl"]
                    team["gf"] = s["gf"]
                    team["ga"] = s["ga"]
                    team["gd"] = s["gd"]

                result.append({
                    "id": f"standings_{slug}_{team['rank']}",
                    "title": f"#{team['rank']} {team['name']}",
                    "summary": f"{league_name} · {season} · {team.get('pts','?')}分 {team.get('wdl','?')}",
                    "url": f"https://m.qiumiwu.com/league/{slug}/standings",
                    "league": league_name,
                    "season": season,
                    "updated": update_time,
                    "rank": team["rank"],
                    "team": team["name"],
                    "logo": team["logo"],
                    "gp": team.get("gp", ""),
                    "pts": team.get("pts", ""),
                    "wdl": team.get("wdl", ""),
                    "gf": team.get("gf", ""),
                    "ga": team.get("ga", ""),
                    "gd": team.get("gd", ""),
                    "score": int(team.get("pts", "0") or "0"),
                    "source_type": "qiumiwu_standings",
                })

        except Exception:
            continue

    return result[:limit]
