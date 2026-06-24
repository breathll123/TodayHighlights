#!/usr/bin/env python3
"""Preview the GitHub "skills" ranking data before wiring it into the app.

Fetches repositories by stars from the GitHub Search API and prints both the
mapped records and a data-quality summary so you can judge whether the source
is good enough — and which query gives the cleanest results.

Stdlib only (urllib), no project deps. A token is optional but raises the
search rate limit from 10 to 30 req/min and avoids occasional 403s.

Usage:
    GITHUB_TOKEN=ghp_xxx python3 scripts/github_skills_preview.py
    python3 scripts/github_skills_preview.py --query "topic:claude-skill" --top 40 --min-stars 100
    python3 scripts/github_skills_preview.py --json > preview.json      # full payload to inspect
    python3 scripts/github_skills_preview.py --compare                  # compare query strategies
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

API = "https://api.github.com"

# Candidate strategies for --compare (what counts as a "skill" repo).
COMPARE_QUERIES = [
    "topic:agent-skills",
    "topic:claude-skill",
    "topic:claude-skills",
    "topic:skills claude",
    "claude skills in:name,description,readme",
]


def _headers() -> dict:
    h = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "today-highlights-skills-preview",
    }
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _get(url: str) -> tuple[dict, dict]:
    req = urllib.request.Request(url, headers=_headers())
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp), dict(resp.headers)


def search(query: str, per_page: int) -> tuple[dict, dict]:
    params = urllib.parse.urlencode(
        {"q": query, "sort": "stars", "order": "desc", "per_page": min(per_page, 100)}
    )
    return _get(f"{API}/search/repositories?{params}")


def _age_days(iso: str | None) -> int | None:
    if not iso:
        return None
    try:
        dt = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return max(0, (datetime.now(timezone.utc) - dt).days)


def map_repo(item: dict, rank: int) -> dict:
    """Shape one search result the way the adapter would, plus quality fields."""
    stars = item.get("stargazers_count", 0)
    created_age = _age_days(item.get("created_at"))
    pushed_age = _age_days(item.get("pushed_at"))
    name = item.get("name", "")
    return {
        "rank": rank,
        "id": item.get("id"),
        "full_name": item.get("full_name", ""),
        "url": item.get("html_url", ""),
        "stars": stars,
        "forks": item.get("forks_count", 0),
        "language": item.get("language") or "—",
        "description": (item.get("description") or "").strip(),
        "topics": item.get("topics", []),
        "archived": item.get("archived", False),
        "created_age_days": created_age,
        "pushed_age_days": pushed_age,
        # Momentum proxy: avg stars/day over the repo's life. Rough, but lets
        # you eyeball "genuinely hot" vs "old and coasting" before you have
        # real weekly-delta history.
        "stars_per_day": round(stars / created_age, 1) if created_age else None,
        "is_awesome": name.lower().startswith("awesome"),
        "desc_len": len((item.get("description") or "").strip()),
    }


def preview(query: str, top: int, min_stars: int, as_json: bool) -> None:
    effective = f"{query} stars:>={min_stars}" if min_stars > 0 else query
    try:
        data, headers = search(effective, top)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "ignore")[:300]
        print(f"HTTP {exc.code} {exc.reason}\n{body}", file=sys.stderr)
        if exc.code in (403, 429):
            print("\nRate limited. Set GITHUB_TOKEN to raise the limit to 30/min.", file=sys.stderr)
        sys.exit(1)

    items = data.get("items", [])[:top]
    rows = [map_repo(it, i + 1) for i, it in enumerate(items)]

    if as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    remaining = headers.get("X-RateLimit-Remaining", "?")
    print(f"query     : {effective!r}")
    print(f"total hits: {data.get('total_count', 0):,}   (showing top {len(rows)})")
    print(f"rate limit: {remaining} search requests remaining this window")
    print(f"auth      : {'token' if os.environ.get('GITHUB_TOKEN') else 'anonymous'}")
    print("=" * 118)
    print(f"{'#':>3}  {'stars':>7} {'/day':>6} {'forks':>6}  {'lang':<12} {'pushed':>7}  {'repo':<38} desc")
    print("-" * 118)
    for r in rows:
        flags = "".join([
            "A" if r["is_awesome"] else " ",
            "Z" if r["archived"] else " ",
            "!" if (r["pushed_age_days"] or 0) > 180 else " ",
        ])
        spd = f"{r['stars_per_day']:>6}" if r["stars_per_day"] is not None else "   —  "
        pushed = f"{r['pushed_age_days']}d" if r["pushed_age_days"] is not None else "—"
        desc = r["description"][:46] or "\033[2m(no description)\033[0m"
        print(f"{r['rank']:>3} {flags}{r['stars']:>7} {spd} {r['forks']:>6}  {r['language']:<12} {pushed:>7}  {r['full_name']:<38} {desc}")

    # ── Quality summary ──
    n = len(rows) or 1
    no_desc = sum(1 for r in rows if r["desc_len"] == 0)
    awesome = sum(1 for r in rows if r["is_awesome"])
    archived = sum(1 for r in rows if r["archived"])
    stale = sum(1 for r in rows if (r["pushed_age_days"] or 0) > 180)
    langs: dict[str, int] = {}
    for r in rows:
        langs[r["language"]] = langs.get(r["language"], 0) + 1
    top_langs = ", ".join(f"{k} {v}" for k, v in sorted(langs.items(), key=lambda x: -x[1])[:6])

    print("=" * 118)
    print("Quality  (flags: A=awesome-list  Z=archived  !=stale >180d)")
    print(f"  empty description : {no_desc}/{n}")
    print(f"  awesome-lists     : {awesome}/{n}   (curated lists, not skills themselves)")
    print(f"  archived          : {archived}/{n}")
    print(f"  stale (>180d push): {stale}/{n}")
    print(f"  languages         : {top_langs}")
    print(f"  median stars/day  : {sorted(r['stars_per_day'] or 0 for r in rows)[n // 2]}")


def compare(top: int, min_stars: int) -> None:
    floor = f" stars:>={min_stars}" if min_stars > 0 else ""
    print(f"Comparing query strategies (sort:stars, floor{floor or ' none'}):\n")
    for q in COMPARE_QUERIES:
        try:
            data, _ = search(q + floor, 5)
        except urllib.error.HTTPError as exc:
            print(f"### {q!r}  HTTP {exc.code} (likely rate limited — set GITHUB_TOKEN)\n")
            continue
        print(f"### {q!r}   total={data.get('total_count', 0):,}")
        for it in data.get("items", [])[:5]:
            desc = (it.get("description") or "")[:54]
            print(f"   {it['stargazers_count']:>7}  {it['full_name']:<40} {desc}")
        print()


def main() -> None:
    ap = argparse.ArgumentParser(description="Preview GitHub skills-by-stars ranking data.")
    ap.add_argument("--query", default="topic:agent-skills", help="GitHub search query (default: topic:agent-skills)")
    ap.add_argument("--top", type=int, default=30, help="how many repos to show (default 30)")
    ap.add_argument("--min-stars", type=int, default=50, help="minimum stars floor (default 50)")
    ap.add_argument("--json", action="store_true", help="dump the mapped records as JSON")
    ap.add_argument("--compare", action="store_true", help="compare several query strategies")
    args = ap.parse_args()

    if args.compare:
        compare(args.top, args.min_stars)
    else:
        preview(args.query, args.top, args.min_stars, args.json)


if __name__ == "__main__":
    main()
