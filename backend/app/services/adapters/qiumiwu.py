import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
from app.core.cache import ttl_cache
from app.core.logging import log_adapter_failure, observed_http_get

_headers = {
    "User-Agent": "Mozilla/5.0 TodayHighlights/0.1",
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


def _media_cache_from_config(config: dict | None):
    return (config or {}).get("_media_cache")


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
def _fetch_matches_raw(limit: int) -> list[dict]:
    """Fetch live match data from qiumiwu schedule API."""
    try:
        resp = observed_http_get(
            httpx.get,
            "https://api.qiumiwu.com/v5/game/schedule/0/1/0/0/0",
            provider="qiumiwu", operation="match_schedule",
            host="api.qiumiwu.com", path="/v5/game/schedule/0/1/0/0/0",
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

    except Exception as exc:
        log_adapter_failure(provider="qiumiwu", operation="match_schedule", stage="parse", exc=exc)
        return []


def _with_match_logo_cache(match: dict, media_cache) -> dict:
    item = dict(match)
    source_entity_id = str(item.get("id") or "")
    league_name = str(item.get("league") or "")
    team_a = str(item.get("team_a") or "")
    team_b = str(item.get("team_b") or "")
    item["logo_league_local"] = _cache_logo(
        media_cache,
        str(item.get("logo_league") or ""),
        entity_type="league",
        entity_name=league_name,
        source_entity_id=source_entity_id,
    )
    item["logo_a_local"] = _cache_logo(
        media_cache,
        str(item.get("logo_a") or ""),
        entity_type="team",
        entity_name=team_a,
        source_entity_id=source_entity_id,
    )
    item["logo_b_local"] = _cache_logo(
        media_cache,
        str(item.get("logo_b") or ""),
        entity_type="team",
        entity_name=team_b,
        source_entity_id=source_entity_id,
    )
    return item


def fetch_matches(config: dict, limit: int) -> list[dict]:
    media_cache = _media_cache_from_config(config)
    return [_with_match_logo_cache(match, media_cache) for match in _fetch_matches_raw(limit)]


fetch_matches.cache_clear = _fetch_matches_raw.cache_clear


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


def _fetch_league(league_name: str, slug: str) -> list[dict]:
    """Fetch and parse standings for a single league. Thread-safe via shared client."""
    try:
        resp = observed_http_get(
            _standings_client.get,
            f"https://m.qiumiwu.com/league/{slug}/standings",
            provider="qiumiwu", operation="standings",
            host="m.qiumiwu.com", path="/league/{slug}/standings",
        )
        resp.raise_for_status()
        html = resp.text

        # Season
        year_m = re.search(r"(\d{4}-\d{4})", html)
        season = year_m.group(1) if year_m else ""

        # Update time
        update_m = re.search(r"(\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{1,2})更新", html)
        update_time = update_m.group(1) if update_m else ""

        # Scope to active tab content
        active_m = re.search(
            r'<div[^>]*active="1"[^>]*>\s*(.*?)(?:<div[^>]*class="[^"]*qmw__tab__item|\Z)',
            html, re.DOTALL,
        )
        tab_html = active_m.group(1) if active_m else html

        # Split by group title blocks
        blocks = re.split(
            r'<div class="stats__table__title">\s*<span>([^<]*)</span>',
            tab_html,
        )[1:]

        # Detect if this is a group-stage tournament (has A-Z groups) or regular league
        group_league = any(re.match(r"^[A-Z]组$", b.strip()) for b in blocks[::2])

        result = []
        for gi in range(0, len(blocks), 2):
            group_title = blocks[gi].strip()  # e.g. "A组" or "总榜"
            block_html = blocks[gi + 1]

            # For regular leagues, only process the first view (总榜)
            if not group_league and gi > 0:
                break

            group_letter = re.match(r"^([A-Z])组$", group_title)
            if not group_letter and group_league:
                continue  # Skip non-group sections only in group tournaments (e.g. "第3名队伍排名")
            group_label = group_letter.group(1) if group_letter else ""

            for m in re.finditer(
                r'<a class="stats__table__list"\s+href="([^"]*)"(?:\s+pos="(\d+)")?[^>]*>\s*'
                r"<span>(\d+)</span>\s*"
                r'<img\s+alt="([^"]*)"\s+src="([^"]*)"[^>]*>\s*'
                r"<span>([^<]*)</span>",
                block_html,
            ):
                rank = int(m.group(3))
                team_name = m.group(6).strip()
                logo_url = m.group(5)

                team_id = f"standings_{slug}_{group_label}_{rank}" if group_label else f"standings_{slug}_{rank}"
                group_display = f"{group_label}组 · " if group_label else ""

                result.append({
                    "id": team_id,
                    "title": f"#{rank} {team_name}",
                    "summary": f"{league_name} · {group_display}{season}",
                    "url": f"https://m.qiumiwu.com/league/{slug}/standings",
                    "league": league_name,
                    "group": group_label,
                    "season": season,
                    "updated": update_time,
                    "rank": rank,
                    "team": team_name,
                    "logo": logo_url,
                    "gp": "—",
                    "pts": "—",
                    "wdl": "—",
                    "gf": "—",
                    "ga": "—",
                    "gd": "—",
                    "score": 0,
                    "source_type": "qiumiwu_standings",
                })

        # Parse stats from each group's own type="info" block
        for gi in range(0, len(blocks), 2):
            group_title = blocks[gi].strip()
            block_html = blocks[gi + 1]
            is_group = bool(re.match(r"^([A-Z])组$", group_title))
            if is_group:
                # Skip the extra "第3名队伍排名" block
                pass
            elif not is_group and group_league:
                continue  # In group tournaments, skip non-letter blocks
            # else: regular league — process the single block
            info_start = block_html.find('type="info"')
            if info_start < 0:
                continue
            info_html = block_html[info_start:]
            # Find stat rows: each <div class="stats__table__list"> with exactly 10 numeric/- spans
            stat_blocks = re.findall(
                r'<div class="stats__table__list">((?:\s*<span[^>]*>\s*[0-9./\-%]+\s*</span>\s*)+)</div>',
                info_html,
            )
            stat_values_for_group = []
            for sb in stat_blocks:
                vals = re.findall(r'<span[^>]*>\s*([0-9./\-%]+)\s*</span>', sb)
                if len(vals) >= 10:
                    stat_values_for_group.append(vals[:10])

            # Filter header row (first span value is non-numeric like "场次" is not matched)
            # Actually the regex already filters non-numeric, so stat_blocks only has data rows

            # Match stats to teams in this group/block
            if is_group:
                gl = re.match(r"^([A-Z])组$", group_title).group(1)
                block_teams = [item for item in result if item.get("group") == gl]
            else:
                block_teams = [item for item in result if not item.get("group")]
            group_teams = block_teams
            for ti, team_item in enumerate(group_teams):
                if ti < len(stat_values_for_group):
                    sv = stat_values_for_group[ti]
                    team_item["gp"] = sv[0].strip()
                    team_item["pts"] = sv[1].strip() if sv[1].strip().replace("-", "").replace(".", "").isdigit() else "0"
                    team_item["wdl"] = sv[2].strip()
                    team_item["gf"] = sv[3].strip()
                    team_item["ga"] = sv[4].strip()
                    team_item["gd"] = sv[5].strip()
                    pts_val = team_item["pts"].replace("-", "0").replace("%", "")
                    try:
                        team_item["score"] = int(float(pts_val))
                    except ValueError:
                        team_item["score"] = 0

        # Update summaries with stats
        for item in result:
            g = item.get("group", "")
            gd = f"{g}组 · " if g else ""
            item["summary"] = f"{item['league']} · {gd}{season} · {item.get('pts','0')}分 {item.get('wdl','—')}"

        return result

    except Exception as exc:
        log_adapter_failure(provider="qiumiwu", operation="standings", stage="parse", exc=exc)
        return []


def fetch_fixtures(config: dict, limit: int) -> list[dict]:
    """Fetch upcoming (fixture-only) matches, sorted by start time ascending."""
    matches = fetch_matches(config, max(limit, 200))
    fixtures = [m for m in matches if m.get("status") == 1]
    fixtures.sort(key=lambda x: x.get("start_time", ""))
    return fixtures[:limit]


@ttl_cache(300, swr=3600)
def _fetch_standings_raw() -> list[dict]:
    """Fetch league standings from qiumiwu mobile pages — all leagues in parallel."""
    all_results = []
    with ThreadPoolExecutor(max_workers=min(len(_STANDINGS_LEAGUES), 8)) as pool:
        futures = {
            pool.submit(_fetch_league, name, slug): slug
            for name, slug in _STANDINGS_LEAGUES.items()
        }
        for future in as_completed(futures):
            all_results.extend(future.result())

    return all_results


def fetch_standings(config: dict, limit: int) -> list[dict]:
    media_cache = _media_cache_from_config(config)
    result = []
    for item in _fetch_standings_raw()[:limit]:
        enriched = dict(item)
        enriched["logo_local"] = _cache_logo(
            media_cache,
            str(enriched.get("logo") or ""),
            entity_type="team",
            entity_name=str(enriched.get("team") or ""),
            source_entity_id=str(enriched.get("id") or ""),
        )
        result.append(enriched)
    return result


fetch_standings.cache_clear = _fetch_standings_raw.cache_clear
