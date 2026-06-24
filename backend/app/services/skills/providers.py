"""Provider registry — maps a skills source to its candidate fetcher and
normalizes each provider's raw output into the generic candidate shape that
`sync_provider` consumes.

Normalized candidate:
    { external_id, name, author, url, language, description,
      popularity, popularity_kind, extra: {...provider-specific...} }
"""
from __future__ import annotations

from app.services.adapters.github import fetch_skill_candidates

# Source.site (the data-source row) -> provider source key (stored on Skill.source)
SITE_TO_SOURCE = {"github_skills": "github"}


def _normalize_github(repo: dict) -> dict:
    return {
        "external_id": str(repo["id"]),
        "name": repo["name"],
        "author": repo["owner"],
        "url": repo["url"],
        "language": repo["language"],
        "description": repo["description"],
        "popularity": repo["stars"],
        "popularity_kind": "stars",
        "extra": {
            "full_name": repo["full_name"],
            "topics": repo["topics"],
            "topics_matched": repo["topics_matched"],
            "forks": repo["forks"],
            "pushed_at": repo["pushed_at"].isoformat() if repo.get("pushed_at") else None,
        },
    }


def fetch_candidates(source: str) -> list[dict]:
    if source == "github":
        return [_normalize_github(repo) for repo in fetch_skill_candidates()]
    raise ValueError(f"unknown skills source: {source}")
