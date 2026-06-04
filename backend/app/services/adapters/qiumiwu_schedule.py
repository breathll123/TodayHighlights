import re
import httpx
from app.core.cache import ttl_cache

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
    """Parse '06-13 星期六' → '2026-06-13'"""
    m = re.match(r"(\d{2})-(\d{2})", date_label)
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
        api_resp = httpx.get(
            "https://api.qiumiwu.com/v5/game/schedule/0/1/0/0/0",
            params={"reqfrom": "web"},
            headers={"User-Agent": "Mozilla/5.0 DailyHighlights/0.1", "Referer": "https://www.qiumiwu.com/"},
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
    except Exception:
        pass
    return _LEAGUE_LOGO_CACHE or logo_map


def _fetch_logos_from_detail(match_id: str) -> tuple[str, str]:
    """Fetch (home_logo, away_logo) from a match detail page."""
    try:
        resp = httpx.get(
            f"https://m.qiumiwu.com/game/{match_id}",
            headers=_HEADERS, timeout=15,
        )
        # Extract team logo img URLs — first two are home and away
        logos = re.findall(r'<img[^>]*src="(https://file\.qiumiwu\.com/team/[^"]+)"[^>]*>', resp.text)
        if len(logos) >= 2:
            return logos[0], logos[1]
    except Exception:
        pass
    return "", ""


def _fill_logo_map(logo_map: dict[str, str], matches_info: list[dict]) -> dict[str, str]:
    """For teams without logos, fetch from their match detail pages."""
    fetched = 0
    for m in matches_info:
        team_a, team_b = m.get("team_a", ""), m.get("team_b", "")
        match_id = m.get("match_id", "")
        need_a = team_a and not logo_map.get(team_a)
        need_b = team_b and not logo_map.get(team_b)

        if (need_a or need_b) and match_id:
            hlogo, alogo = _fetch_logos_from_detail(match_id)
            if hlogo and team_a not in logo_map:
                logo_map[team_a] = hlogo
            if alogo and team_b not in logo_map:
                logo_map[team_b] = alogo
            fetched += 1
            if fetched >= 20:
                break
    return logo_map


@ttl_cache(600)
def fetch_competition_schedule(config: dict, limit: int) -> list[dict]:
    """Fetch competition schedule from qiumiwu mobile HTML."""
    comp_name = (config or {}).get("competition", "男足世界杯")
    slug = _COMPETITIONS.get(comp_name)
    if not slug:
        return []

    try:
        resp = httpx.get(
            f"https://m.qiumiwu.com/game/{slug}",
            headers=_HEADERS, timeout=20, follow_redirects=True,
        )
        resp.raise_for_status()
        html = resp.text

        logo_map = _get_logo_map()
        league_logo = logo_map.get(f"_league_{comp_name}", "")

        # Parse once: collect date headers and matches
        result = []
        current_date = ""
        matches_info = []

        tokens = list(re.finditer(
            r'(?:<div class="fixture__details__header">\s*<span>(\d{2}-\d{2}\s+\S+)</span>)|'
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
                    "status": 1,
                    "status_name": "未开赛",
                    "team_a": team_a,
                    "team_b": team_b,
                    "logo_a": logo_map.get(team_a, ""),
                    "logo_b": logo_map.get(team_b, ""),
                    "score_a": "",
                    "score_b": "",
                    "minute": "",
                    "start_time": start_iso,
                    "group": group,
                    "round": round_num,
                    "score": 0,
                    "source_type": "qiumiwu_schedule",
                })

        return result[:limit]

    except Exception:
        return []
