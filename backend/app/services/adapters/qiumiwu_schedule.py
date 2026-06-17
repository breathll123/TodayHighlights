import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
from app.core.logging import log_adapter_failure, observed_http_get

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
}

_COMPETITIONS = {
    "男足世界杯": "nanzushijiebei",
    "女足世界杯": "nvzushijiebei",
    "欧洲杯": "ouzhoubei",
    "美洲杯": "meizhoubei",
    "亚洲杯": "yazhoubei",
    "欧冠": "ouguanbei",
    "欧联杯": "oulianbei",
    "英超": "yingchao",
    "西甲": "xijia",
    "意甲": "yijia",
    "德甲": "dejia",
    "法甲": "fajia",
    "中超": "zhongchao",
}


def _parse_date(date_label: str) -> str:
    """Parse '明天 06-13 星期六' or '06-13 星期六' → '2026-06-13'"""
    m = re.search(r"(\d{2})-(\d{2})", date_label)
    if m:
        return f"2026-{m.group(1)}-{m.group(2)}"
    return ""


_LEAGUE_LOGO_CACHE: dict[str, str] = {}
_LOGO_CACHE_TS = 0


def _get_logo_map() -> dict[str, str]:
    """Fetch team name → logo mapping from main schedule API. Cached for 5min."""
    import time as _time
    global _LEAGUE_LOGO_CACHE, _LOGO_CACHE_TS
    now = _time.time()
    if _LEAGUE_LOGO_CACHE and (now - _LOGO_CACHE_TS) < 300:
        return _LEAGUE_LOGO_CACHE

    logo_map = {}
    try:
        api_resp = observed_http_get(
            httpx.get,
            "https://api.qiumiwu.com/v5/game/schedule/0/1/0/0/0",
            provider="qiumiwu", operation="schedule_logo_map",
            host="api.qiumiwu.com", path="/v5/game/schedule/0/1/0/0/0",
            params={"reqfrom": "web"},
            headers={"User-Agent": "Mozilla/5.0 TodayHighlights/0.1", "Referer": "https://www.qiumiwu.com/"},
            timeout=20,
        )
        api_data = api_resp.json()
        for m in api_data.get("data", {}).get("list", []) or []:
            home = m.get("home", {})
            away = m.get("away", {})
            hname = home.get("name", "")
            aname = away.get("name", "")
            if hname:
                logo_map[hname] = home.get("logo", "")
            if aname:
                logo_map[aname] = away.get("logo", "")
            league = m.get("league", {})
            lname = league.get("name", "")
            llogo = league.get("logo", "")
            if lname and llogo and lname not in logo_map:
                logo_map[f"_league_{lname}"] = llogo
        _LEAGUE_LOGO_CACHE = logo_map
        _LOGO_CACHE_TS = now
    except Exception as exc:
        log_adapter_failure(provider="qiumiwu", operation="schedule_logo_map", stage="parse", exc=exc)
    return _LEAGUE_LOGO_CACHE or logo_map


def _fetch_logos_from_detail(match_id: str) -> tuple[str, str]:
    """Fetch (home_logo, away_logo) from a match detail page."""
    try:
        resp = observed_http_get(
            httpx.get,
            f"https://m.qiumiwu.com/game/{match_id}",
            provider="qiumiwu", operation="match_detail_logos",
            host="m.qiumiwu.com", path="/game/{match_id}",
            headers=_HEADERS, timeout=15,
        )
        # Extract team logo img URLs — first two are home and away
        logos = re.findall(r'<img[^>]*src="(https://file\.qiumiwu\.com/team/[^"]+)"[^>]*>', resp.text)
        if len(logos) >= 2:
            return logos[0], logos[1]
    except Exception as exc:
        log_adapter_failure(provider="qiumiwu", operation="match_detail_logos", stage="parse", exc=exc)
    return "", ""


def _fill_logo_map(logo_map: dict[str, str], matches_info: list[dict]) -> dict[str, str]:
    """For teams without logos, fetch from their match detail pages IN PARALLEL (max 4 workers)."""
    # Collect unique missing match_ids
    to_fetch: dict[str, dict] = {}  # match_id -> {"team_a": ..., "team_b": ...}
    for m in matches_info:
        team_a, team_b = m.get("team_a", ""), m.get("team_b", "")
        match_id = m.get("match_id", "")
        if not match_id:
            continue
        need_a = team_a and not logo_map.get(team_a)
        need_b = team_b and not logo_map.get(team_b)
        if (need_a or need_b) and match_id not in to_fetch:
            to_fetch[match_id] = {"team_a": team_a, "team_b": team_b}

    # Fetch logos in parallel (max 20 match_ids)
    fetch_ids = list(to_fetch.keys())[:20]
    if not fetch_ids:
        return logo_map

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(_fetch_logos_from_detail, mid): mid for mid in fetch_ids}
        for future in as_completed(futures):
            mid = futures[future]
            info = to_fetch[mid]
            try:
                hlogo, alogo = future.result(timeout=10)
            except Exception:
                continue
            if hlogo and info["team_a"] not in logo_map:
                logo_map[info["team_a"]] = hlogo
            if alogo and info["team_b"] not in logo_map:
                logo_map[info["team_b"]] = alogo

    return logo_map


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
        metadata={"adapter": "qiumiwu_schedule"},
    )


def fetch_competition_schedule(config: dict, limit: int) -> list[dict]:
    """Fetch competition schedule (fixtures) + include completed matches from live API."""
    comp_name = (config or {}).get("competition", "男足世界杯")
    media_cache = (config or {}).get("_media_cache")
    slug = _COMPETITIONS.get(comp_name)
    if not slug:
        return []

    # Map competition names to league names used in live API
    _COMP_LEAGUE = {
        "男足世界杯": "男足世界杯",
    }
    league_filter = _COMP_LEAGUE.get(comp_name, comp_name)

    result: list[dict] = []

    # 1. Fetch completed/live matches from live API
    try:
        from app.services.adapters.qiumiwu import _fetch_matches_raw
        live_matches = _fetch_matches_raw(200)
        for m in live_matches:
            if m.get("league") == league_filter and m.get("status") != 1:
                # Map status fields to match schedule format
                result.append({
                    **m,
                    "logo_a_local": _cache_logo(media_cache, m.get("logo_a", ""), entity_type="team", entity_name=m.get("team_a", ""), source_entity_id=str(m.get("id", ""))),
                    "logo_b_local": _cache_logo(media_cache, m.get("logo_b", ""), entity_type="team", entity_name=m.get("team_b", ""), source_entity_id=str(m.get("id", ""))),
                    "logo_league_local": _cache_logo(media_cache, m.get("logo_league", ""), entity_type="league", entity_name=comp_name, source_entity_id=str(m.get("id", ""))),
                })
    except Exception as exc:
        log_adapter_failure(provider="qiumiwu", operation="live_schedule_merge", stage="parse", exc=exc)

    try:
        resp = observed_http_get(
            httpx.get,
            f"https://m.qiumiwu.com/game/{slug}",
            provider="qiumiwu", operation="competition_schedule",
            host="m.qiumiwu.com", path="/game/{slug}",
            headers=_HEADERS, timeout=20, follow_redirects=True,
        )
        resp.raise_for_status()
        html = resp.text

        logo_map = _get_logo_map()
        league_logo = logo_map.get(f"_league_{comp_name}", "")

        # Parse once: collect date headers and matches (keep live matches already in result)
        current_date = ""
        matches_info = []

        tokens = list(re.finditer(
            r'(?:<div class="fixture__details__header">\s*<span>([^<]+)</span>)|'
            r'(?:fixture__list__header">\s*<span>(\d{2}:\d{2})</span>.*?<span>([^<]*)</span>\s*</div>\s*'
            r'<a[^>]*class="fixture__list__info"\s*href="/game/(\d+)"[^>]*>\s*'
            r'<div[^>]*class="fixture__list__team"[^>]*><span>([^<]+)</span>\s*</div>\s*'
            r'<div[^>]*class="fixture__list__score"[^>]*>\s*[^<]*</div>\s*'
            r'<div[^>]*class="fixture__list__team"[^>]*><span>([^<]+)</span>)',
            html,
            re.DOTALL,
        ))

        # First pass: collect match info for logo fetching
        for tok in tokens:
            if tok.group(2):  # Match
                matches_info.append({
                    "team_a": tok.group(5),
                    "team_b": tok.group(6),
                    "match_id": tok.group(4),
                })
        logo_map = _fill_logo_map(logo_map, matches_info)

        for tok in tokens:
            if tok.group(1):  # Date header
                current_date = _parse_date(tok.group(1))
            elif tok.group(2):  # Match
                time_str = tok.group(2)
                group_round = tok.group(3).strip()
                match_id = tok.group(4)
                team_a = tok.group(5)
                team_b = tok.group(6)

                group, round_num = "", ""
                gr_m = re.match(r"([A-Z])组\s*第(\d+)轮", group_round)
                if gr_m:
                    group = gr_m.group(1)
                    round_num = gr_m.group(2)
                elif "决赛" in group_round:
                    round_num = group_round
                else:
                    group = group_round

                start_iso = f"{current_date}T{time_str}:00" if current_date else ""

                # Use group+round as "league" so MatchList groups by stage
                stage_label = f"{group}组" if group else (round_num or comp_name)

                result.append({
                    "id": f"schedule_{slug}_{match_id}",
                    "title": f"{team_a} vs {team_b}",
                    "summary": f"{round_num or group_round} · {time_str}",
                    "url": f"https://m.qiumiwu.com/game/{match_id}" if match_id else "",
                    "league": stage_label,
                    "logo_league": league_logo,
                    "logo_league_local": _cache_logo(media_cache, league_logo, entity_type="league", entity_name=comp_name, source_entity_id=str(match_id)),
                    "status": 1,
                    "status_name": "未开赛",
                    "team_a": team_a,
                    "team_b": team_b,
                    "logo_a": logo_map.get(team_a, ""),
                    "logo_a_local": _cache_logo(media_cache, logo_map.get(team_a, ""), entity_type="team", entity_name=team_a, source_entity_id=str(match_id)),
                    "logo_b": logo_map.get(team_b, ""),
                    "logo_b_local": _cache_logo(media_cache, logo_map.get(team_b, ""), entity_type="team", entity_name=team_b, source_entity_id=str(match_id)),
                    "score_a": "",
                    "score_b": "",
                    "minute": "",
                    "start_time": start_iso,
                    "group": group,
                    "round": round_num,
                    "score": 0,
                    "source_type": "qiumiwu_schedule",
                })

        # Dedup by match_id (live matches may overlap with HTML fixtures)
        seen: set[str] = set()
        deduped: list[dict] = []
        for r in result:
            mid = str(r.get("id", ""))
            if mid and mid not in seen:
                seen.add(mid)
                deduped.append(r)
            elif not mid:
                deduped.append(r)

        deduped.sort(key=lambda x: x.get("start_time", ""))
        return deduped[:limit]

    except Exception as exc:
        log_adapter_failure(provider="qiumiwu", operation="competition_schedule", stage="parse", exc=exc)
        return result if result else []
