import re
import httpx
from app.core.cache import ttl_cache

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
}

# Competition slugs the user cares about
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

        result = []

        # Parse match blocks:
        # fixture__list__header: <span>TIME</span> ... <span>GROUP ROUND</span>
        # fixture__list__info: <a href="/game/ID"><div><span>TEAM_A</span></div><div></div><div><span>TEAM_B</span></div></a>
        match_blocks = re.findall(
            r'<div class="fixture__list__header">\s*<span>(\d{2}:\d{2})</span>.*?<span>([^<]*)</span>\s*</div>\s*'
            r'<a[^>]*class="fixture__list__info"\s*href="/game/(\d+)"[^>]*>\s*'
            r'<div[^>]*class="fixture__list__team"[^>]*><span>([^<]+)</span>\s*</div>\s*'
            r'<div[^>]*class="fixture__list__score"[^>]*>\s*[^<]*</div>\s*'
            r'<div[^>]*class="fixture__list__team"[^>]*><span>([^<]+)</span>',
            html,
            re.DOTALL,
        )

        for m in match_blocks:
            time_str = m[0]
            group_round = m[1].strip()
            match_id = m[2]
            team_a = m[3]
            team_b = m[4]

            # Parse group + round
            group = ""
            round_num = ""
            # Handle "A组 第1轮 小组赛", "I组 第1轮 小组赛", "1/8决赛", "半决赛", "决赛" etc.
            gr_m = re.match(r"([A-Z])组\s*第(\d+)轮", group_round)
            if gr_m:
                group = gr_m.group(1)
                round_num = gr_m.group(2)
            elif "决赛" in group_round:
                round_num = group_round
            else:
                group = group_round

            result.append({
                "id": f"schedule_{slug}_{match_id}",
                "title": f"{team_a} vs {team_b}",
                "summary": f"{comp_name} · {group_round} · {time_str}",
                "url": f"https://m.qiumiwu.com/game/{match_id}" if match_id else "",
                "competition": comp_name,
                "group": group,
                "round": round_num,
                "time": time_str,
                "team_a": team_a,
                "team_b": team_b,
                "score": 0,
                "source_type": "qiumiwu_schedule",
            })

        return result[:limit]

    except Exception:
        return []
