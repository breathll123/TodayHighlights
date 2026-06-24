"""GitHub repository search adapter — fetches skill-topic candidates by stars.

Used by the daily sync (not by request-time block resolution, which reads the
DB). Runs the configured skill topics, merges and de-dupes by repo id, applies
a stars floor, and returns the top-K by stars for downstream LLM filtering.
"""
from __future__ import annotations

from datetime import datetime, timezone

import httpx

from app.core.config import settings
from app.core.logging import log_adapter_failure, observed_http_get

_API = "https://api.github.com"
_PER_PAGE = 100


def _headers() -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "today-highlights/0.1",
    }
    token = (settings.github_token or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _parse_pushed_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _normalize(item: dict, topic: str) -> dict:
    owner = (item.get("owner") or {}).get("login", "")
    return {
        "id": item["id"],
        "full_name": item.get("full_name", ""),
        "owner": owner,
        "name": item.get("name", ""),
        "url": item.get("html_url", ""),
        "language": item.get("language") or "",
        "topics": item.get("topics", []) or [],
        "topics_matched": [topic],
        "stars": item.get("stargazers_count", 0),
        "forks": item.get("forks_count", 0),
        "pushed_at": _parse_pushed_at(item.get("pushed_at")),
        "description": (item.get("description") or "").strip(),
    }


def _search_topic(topic: str, min_stars: int, max_results: int) -> list[dict]:
    """One topic, sorted by stars desc, paginated up to max_results."""
    query = f"{topic} stars:>={min_stars}" if min_stars > 0 else topic
    results: list[dict] = []
    page = 1
    while len(results) < max_results:
        try:
            resp = observed_http_get(
                httpx.get,
                f"{_API}/search/repositories",
                provider="github", operation="skill_search",
                host="api.github.com", path="/search/repositories",
                params={
                    "q": query, "sort": "stars", "order": "desc",
                    "per_page": _PER_PAGE, "page": page,
                },
                headers=_headers(),
                timeout=30,
                follow_redirects=True,
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
        except Exception as exc:  # noqa: BLE001 — log + stop this topic, keep what we have
            log_adapter_failure(provider="github", operation="skill_search", stage="fetch", exc=exc)
            break
        if not items:
            break
        results.extend(_normalize(it, topic) for it in items)
        if len(items) < _PER_PAGE:
            break
        page += 1
    return results[:max_results]


def fetch_skill_candidates(
    topics: list[str] | None = None,
    min_stars: int | None = None,
    top_k: int | None = None,
) -> list[dict]:
    """Run every skill topic, merge by repo id (recording which topics matched),
    and return the top-K candidates by stars."""
    if topics is None:
        topics = [t.strip() for t in settings.github_skills_topics.split(",") if t.strip()]
    if min_stars is None:
        min_stars = settings.github_skills_min_stars
    if top_k is None:
        top_k = settings.github_skills_top_k

    merged: dict[int, dict] = {}
    for topic in topics:
        for repo in _search_topic(topic, min_stars, top_k):
            existing = merged.get(repo["id"])
            if existing is None:
                merged[repo["id"]] = repo
            else:
                existing["topics_matched"] = sorted(set(existing["topics_matched"]) | {topic})
                existing["stars"] = max(existing["stars"], repo["stars"])

    candidates = sorted(merged.values(), key=lambda r: r["stars"], reverse=True)
    return candidates[:top_k]
