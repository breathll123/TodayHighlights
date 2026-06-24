from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.entities import GithubSkillRepo, PageBlock
from app.services.adapters import github
from app.services.blocks import resolve_block_data
from app.services.github_skills import _has_chinese


def _repo(rid: int, stars: int, topic: str) -> dict:
    """A normalized candidate as adapters.github._search_topic would emit."""
    return {
        "id": rid, "full_name": f"owner{rid}/repo{rid}", "owner": f"owner{rid}",
        "name": f"repo{rid}", "url": f"https://github.com/owner{rid}/repo{rid}",
        "language": "Python", "topics": [], "topics_matched": [topic],
        "stars": stars, "forks": 0, "pushed_at": None, "description": "",
    }


def test_block_returns_only_kept_skills_sorted_by_stars() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as session:
        session.add_all([
            GithubSkillRepo(id=1, full_name="o/alpha", owner="o", name="alpha", url="https://gh/alpha",
                            stars=500, description_zh="中文 A", is_skill=True, status="active"),
            GithubSkillRepo(id=2, full_name="o/beta", owner="o", name="beta", url="https://gh/beta",
                            stars=900, description_zh="中文 B", is_skill=True, status="active"),
            GithubSkillRepo(id=3, full_name="o/collection", owner="o", name="collection", url="https://gh/c",
                            stars=2000, is_skill=False, status="active"),   # dropped by filter
            GithubSkillRepo(id=4, full_name="o/removed", owner="o", name="removed", url="https://gh/r",
                            stars=1500, description_zh="x", is_skill=True, status="removed"),  # dormant
            GithubSkillRepo(id=5, full_name="o/unclassified", owner="o", name="unclassified", url="https://gh/u",
                            stars=3000, is_skill=None, status="active"),    # not yet classified
        ])
        block = PageBlock(
            page_route="/topics/ai", title="GitHub Skills", source_type="github_skills",
            source_config={}, display_count=10, status="published",
        )
        session.add(block)
        session.commit()

        result = resolve_block_data(session, block)

    # Only kept + active skills, highest stars first.
    assert [r["title"] for r in result] == ["beta", "alpha"]
    assert result[0]["score"] == 900
    assert result[0]["owner"] == "o"
    assert result[0]["summary"] == "中文 B"
    assert result[0]["url"] == "https://gh/beta"
    assert result[0]["rank"] == 1


def test_published_block_resolves_through_get_page_blocks() -> None:
    """github_skills is DB-backed, so get_page_blocks must resolve it with the
    session (db_types) — not the live path that passes session=None."""
    from app.services.blocks import get_page_blocks

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as session:
        session.add(GithubSkillRepo(id=1, full_name="o/alpha", owner="o", name="alpha",
                                    url="https://gh/alpha", stars=500, description_zh="中文",
                                    is_skill=True, status="active"))
        session.add(PageBlock(page_route="/topics/ai", title="GitHub Skills", source_type="github_skills",
                              source_config={}, display_count=10, status="published", enabled=True,
                              grid_x=0, grid_y=0))
        session.commit()

        result = get_page_blocks(session, "/topics/ai")

    blocks = [b for b in result if b["source_type"] == "github_skills"]
    assert len(blocks) == 1
    assert [d["title"] for d in blocks[0]["data"]] == ["alpha"]


def test_fetch_candidates_merges_and_dedupes(monkeypatch) -> None:
    canned = {
        "topic:a": [_repo(1, 100, "topic:a"), _repo(2, 300, "topic:a")],
        "topic:b": [_repo(2, 300, "topic:b"), _repo(3, 200, "topic:b")],
    }
    monkeypatch.setattr(github, "_search_topic", lambda topic, min_stars, max_results: canned.get(topic, []))

    out = github.fetch_skill_candidates(topics=["topic:a", "topic:b"], min_stars=0, top_k=10)

    # Deduped by id, sorted by stars desc.
    assert [r["id"] for r in out] == [2, 3, 1]
    repo2 = next(r for r in out if r["id"] == 2)
    assert sorted(repo2["topics_matched"]) == ["topic:a", "topic:b"]


def test_has_chinese() -> None:
    assert _has_chinese("生成幻灯片的 skill") is True
    assert _has_chinese("Browser automation CLI") is False


def test_sync_enable_flag_roundtrip() -> None:
    from app.services.github_skills import is_sync_enabled, set_sync_enabled

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as session:
        assert is_sync_enabled(session) is False  # default off
        set_sync_enabled(session, True)
        assert is_sync_enabled(session) is True
        set_sync_enabled(session, False)
        assert is_sync_enabled(session) is False


def test_block_updated_at_uses_last_synced(monkeypatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as session:
        synced = datetime(2026, 6, 24, 4, 0, 0)
        session.add(GithubSkillRepo(id=1, full_name="o/a", owner="o", name="a", url="https://gh/a",
                                    stars=10, is_skill=True, status="active", last_synced_at=synced))
        block = PageBlock(page_route="/topics/ai", title="GitHub Skills", source_type="github_skills",
                          source_config={}, display_count=5, status="published")
        session.add(block)
        session.commit()

        from app.services.blocks import _source_last_crawled_at

        assert _source_last_crawled_at(session, block) == synced
