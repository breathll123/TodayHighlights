from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.entities import PageBlock, Skill
from app.services.adapters import github
from app.services.blocks import resolve_block_data, get_page_blocks
from app.services.skills.classify import has_chinese
from app.services.skills.prompts import classify_prompt_version
from app.services.skills.sync import needs_reclassify


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _skill(ext: str, name: str, popularity: int, *, is_skill, status="active", desc_zh="中文") -> Skill:
    return Skill(source="github", external_id=ext, name=name, author="o",
                 url=f"https://gh/{name}", popularity=popularity, popularity_kind="stars",
                 description_zh=desc_zh, is_skill=is_skill, status=status)


def test_block_returns_only_kept_skills_sorted_by_popularity() -> None:
    with _session() as s:
        s.add_all([
            _skill("1", "alpha", 500, is_skill=True),
            _skill("2", "beta", 900, is_skill=True),
            _skill("3", "collection", 2000, is_skill=False),     # dropped by filter
            _skill("4", "removed", 1500, is_skill=True, status="removed"),
            _skill("5", "unclassified", 3000, is_skill=None),    # not yet classified
        ])
        block = PageBlock(page_route="/topics/ai", title="GitHub Skills", source_type="github_skills",
                          source_config={}, display_count=10, status="published")
        s.add(block)
        s.commit()
        result = resolve_block_data(s, block)

    assert [r["title"] for r in result] == ["beta", "alpha"]
    assert result[0]["score"] == 900
    assert result[0]["owner"] == "o"
    assert result[0]["summary"] == "中文"
    assert result[0]["rank"] == 1


def test_published_block_resolves_through_get_page_blocks() -> None:
    """github_skills is DB-backed; get_page_blocks must resolve it with the
    session (db_types), not the live path that passes session=None."""
    with _session() as s:
        s.add(_skill("1", "alpha", 500, is_skill=True))
        s.add(PageBlock(page_route="/topics/ai", title="GitHub Skills", source_type="github_skills",
                        source_config={}, display_count=10, status="published", enabled=True, grid_x=0, grid_y=0))
        s.commit()
        result = get_page_blocks(s, "/topics/ai")

    blocks = [b for b in result if b["source_type"] == "github_skills"]
    assert len(blocks) == 1
    assert [d["title"] for d in blocks[0]["data"]] == ["alpha"]


def test_prompt_change_triggers_reclassify() -> None:
    v1 = classify_prompt_version("prompt A")
    v2 = classify_prompt_version("prompt B")
    assert v1 != v2
    skill = Skill(source="github", external_id="1", is_skill=True, classify_prompt_version=v1, description="x")
    assert needs_reclassify(skill, v1) is False
    assert needs_reclassify(skill, v2) is True          # prompt changed -> reclassify
    skill.is_skill = None
    assert needs_reclassify(skill, v1) is True          # never classified -> reclassify


def test_fetch_candidates_merges_and_dedupes(monkeypatch) -> None:
    def _repo(rid: int, stars: int, topic: str) -> dict:
        return {"id": rid, "full_name": f"o/{rid}", "owner": "o", "name": str(rid), "url": "",
                "language": "Python", "topics": [], "topics_matched": [topic], "stars": stars,
                "forks": 0, "pushed_at": None, "description": ""}
    canned = {
        "topic:a": [_repo(1, 100, "topic:a"), _repo(2, 300, "topic:a")],
        "topic:b": [_repo(2, 300, "topic:b"), _repo(3, 200, "topic:b")],
    }
    monkeypatch.setattr(github, "_search_topic", lambda topic, min_stars, max_results: canned.get(topic, []))
    out = github.fetch_skill_candidates(topics=["topic:a", "topic:b"], min_stars=0, top_k=10)
    assert [r["id"] for r in out] == [2, 3, 1]
    repo2 = next(r for r in out if r["id"] == 2)
    assert sorted(repo2["topics_matched"]) == ["topic:a", "topic:b"]


def test_has_chinese() -> None:
    assert has_chinese("生成幻灯片的 skill") is True
    assert has_chinese("Browser automation CLI") is False


def test_block_updated_at_uses_last_synced() -> None:
    from app.services.blocks import _source_last_crawled_at

    with _session() as s:
        synced = datetime(2026, 6, 24, 4, 0, 0)
        skill = _skill("1", "a", 10, is_skill=True)
        skill.last_synced_at = synced
        s.add(skill)
        block = PageBlock(page_route="/topics/ai", title="GitHub Skills", source_type="github_skills",
                          source_config={}, display_count=5, status="published")
        s.add(block)
        s.commit()
        assert _source_last_crawled_at(s, block) == synced
