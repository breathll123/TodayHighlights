import re
from concurrent.futures import ThreadPoolExecutor, as_completed

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


def _cache_logo(media_cache, url: str, *, entity_type: str, entity_name: str, source_entity_id: str) -> str:
    if not media_cache or not url:
        return ""
    return media_cache.cache_remote_image(
        url,
        provider="qiumiwu",
        entity_type=entity_type,
        entity_name=entity_name,
        source_entity_id=source_entity_id,
        asset_type="football_logo",
        metadata={"adapter": "qiumiwu"},
    )


@ttl_cache(30, swr=300)
def fetch_matches(_config: dict, limit: int, media_cache=None) -> list[dict]:
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

            # scores array: [home_stats], [away_stats]
            # Each stats: [ft, ht, ?, ?, ?, ?, corners, ?, ?]
            home_score = str(scores[0][0]) if scores and len(scores) > 0 and scores[0] else ""
            away_score = str(scores[1][0]) if scores and len(scores) > 1 and scores[1] else ""
            home_ht = str(scores[0][1]) if scores and len(scores) > 0 and len(scores[0]) > 1 else ""
            away_ht = str(scores[1][1]) if scores and len(scores) > 1 and len(scores[1]) > 1 else ""

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
                "logo_league_local": _cache_logo(media_cache, league.get("logo", ""), entity_type="league", entity_name=league_name, source_entity_id=str(match_id)),
                "status": status,
                "status_name": status_name,
                "team_a": home.get("name", ""),
                "team_b": away.get("name", ""),
                "logo_a": home.get("logo", ""),
                "logo_a_local": _cache_logo(media_cache, home.get("logo", ""), entity_type="team", entity_name=home.get("name", ""), source_entity_id=str(match_id)),
                "logo_b": away.get("logo", ""),
                "logo_b_local": _cache_logo(media_cache, away.get("logo", ""), entity_type="team", entity_name=away.get("name", ""), source_entity_id=str(match_id)),
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
    "法甲": "fajia", "荷甲": "hejia", "葡超": "puchao", "瑞典超": "ruidianchao",
    "世界杯": "nanzushijiebei",
    "欧冠": "ouguanbei", "欧联杯": "oulianbei",
    "中超": "zhongchao",
    "亚冠精英": "yaguanjingying", "亚冠二级": "yaguanerji",
    "英冠": "yingguan", "英甲": "yingjia",
    "巴甲": "bajia", "澳超": "aochao",
    "欧洲杯": "ouzhoubei", "美洲杯": "meizhoubei", "非洲杯": "feizhoubei",
}

_STANDINGS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
}

# Module-level client for connection pooling across parallel league fetches
_standings_client = httpx.Client(
    timeout=20,
    headers=_STANDINGS_HEADERS,
)


def _fetch_league(league_name: str, slug: str, media_cache=None) -> list[dict]:
    """Fetch and parse standings for a single league. Thread-safe via shared client."""
    try:
        resp = _standings_client.get(
            f"https://m.qiumiwu.com/league/{slug}/standings",
        )
        resp.raise_for_status()
        html = resp.text

        # Season — try "2024-2025" first, fall back to single year "2026"
        year_m = re.search(r"(\d{4}-\d{4})", html)
        if year_m:
            season = year_m.group(1)
        else:
            year_m2 = re.search(r"(\d{4})赛季", html)
            season = year_m2.group(1) if year_m2 else ""

        # Update time
        update_m = re.search(r"(\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{1,2})更新", html)
        update_time = update_m.group(1) if update_m else ""

        # Parse group labels (for group-stage tournaments like World Cup)
        group_labels = []
        for gm in re.finditer(r"([A-Z])组", html):
            label = gm.group(1)
            if not group_labels or group_labels[-1] != label:
                group_labels.append(label)

        # Collect teams. For regular leagues (no groups), only take the first view (总榜).
        # Group tournaments (World Cup etc.) keep all ranks across groups.
        teams = []
        seen_ranks = set()
        for m in re.finditer(
            r'<a class="stats__table__list"\s+href="([^"]*)"(?:\s+pos="(\d+)")?[^>]*>\s*'
            r"<span>(\d+)</span>\s*"
            r'<img\s+alt="([^"]*)"\s+src="([^"]*)"[^>]*>\s*'
            r"<span>([^<]*)</span>",
            html,
        ):
            rank = int(m.group(3))
            # For regular leagues (no groups), dedup by rank (only 总榜)
            if not group_labels and rank in seen_ranks:
                continue
            seen_ranks.add(rank)
            teams.append({
                "rank": rank,
                "name": m.group(6),
                "logo": m.group(5),
            })

        # Stats — per-team rows in type="info" section
        info_start = html.find('type="info"')
        if info_start < 0:
            return []

        info_html = html[info_start:]
        stat_rows = re.findall(
            r'<div class="stats__table__list">((?:\s*<span[^>]*>[^<]*</span>\s*)+)</div>',
            info_html,
        )

        stats_list = []
        for row_html in stat_rows:
            values = re.findall(r"<span[^>]*>\s*([0-9./\-]+[%]?)\s*</span>", row_html)
            if len(values) == 10 and values[0].strip().isdigit():
                if len(stats_list) >= len(teams):
                    break  # Only take 总榜 stats for regular leagues
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

        # Match teams with stats by position index
        result = []
        teams_per_group = len(teams) // len(group_labels) if group_labels else 0
        for i, team in enumerate(teams):
            if i < len(stats_list):
                s = stats_list[i]
                team["gp"] = s["gp"]
                team["pts"] = s["pts"]
                team["wdl"] = s["wdl"]
                team["gf"] = s["gf"]
                team["ga"] = s["ga"]
                team["gd"] = s["gd"]

            # Assign group label if available
            group = ""
            if group_labels and teams_per_group > 0:
                group_idx = i // teams_per_group
                if group_idx < len(group_labels):
                    group = group_labels[group_idx]
                team["group"] = group

            # Build ID — include group to avoid collisions in group tournaments
            team_id = f"standings_{slug}_{group}_{team['rank']}" if group else f"standings_{slug}_{team['rank']}"

            # Build summary — include group label
            group_prefix = f"{group}组 · " if group else ""
            result.append({
                "id": team_id,
                "title": f"#{team['rank']} {team['name']}",
                "summary": f"{league_name} · {group_prefix}{season} · {team.get('pts','?')}分 {team.get('wdl','?')}",
                "url": f"https://m.qiumiwu.com/league/{slug}/standings",
                "league": league_name,
                "group": group,
                "season": season,
                "updated": update_time,
                "rank": team["rank"],
                "team": team["name"],
                "logo": team["logo"],
                "logo_local": _cache_logo(media_cache, team["logo"], entity_type="team", entity_name=team["name"], source_entity_id=team_id),
                "gp": team.get("gp", ""),
                "pts": team.get("pts", ""),
                "wdl": team.get("wdl", ""),
                "gf": team.get("gf", ""),
                "ga": team.get("ga", ""),
                "gd": team.get("gd", ""),
                "score": int(team.get("pts", "0") or "0"),
                "source_type": "qiumiwu_standings",
            })

        return result

    except Exception:
        return []


@ttl_cache(60)
def fetch_fixtures(config: dict, limit: int, media_cache=None) -> list[dict]:
    """Fetch upcoming (fixture-only) matches, sorted by start time ascending."""
    matches = fetch_matches(config, max(limit, 200), media_cache=media_cache)
    fixtures = [m for m in matches if m.get("status") == 1]
    fixtures.sort(key=lambda x: x.get("start_time", ""))
    return fixtures[:limit]


@ttl_cache(300, swr=3600)
def fetch_standings(_config: dict, limit: int, media_cache=None) -> list[dict]:
    """Fetch league standings from qiumiwu mobile pages — all leagues in parallel."""
    all_results = []
    with ThreadPoolExecutor(max_workers=min(len(_STANDINGS_LEAGUES), 8)) as pool:
        futures = {
            pool.submit(_fetch_league, name, slug, media_cache): slug
            for name, slug in _STANDINGS_LEAGUES.items()
        }
        for future in as_completed(futures):
            all_results.extend(future.result())

    return all_results[:limit]
