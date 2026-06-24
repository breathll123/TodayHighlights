#!/usr/bin/env python3
"""Run one GitHub skills sync manually (initial backfill or on demand).

Fetches candidates, classifies + translates via your default AIModelConfig, and
writes github_skill_repos / github_skill_stats. Run from the backend dir with
the project Python env and a populated .env:

    python3 scripts/github_skills_sync.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal  # noqa: E402
from app.services.github_skills import sync_github_skills  # noqa: E402


def main() -> None:
    with SessionLocal() as session:
        summary = sync_github_skills(session)
    print(f"done: {summary}")


if __name__ == "__main__":
    main()
