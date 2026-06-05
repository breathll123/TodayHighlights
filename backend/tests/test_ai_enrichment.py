from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.database import get_session
from app.models.entities import AIItemEnrichment, RawItem, Source, Topic
from app.services.ai_enrichment import select_item_candidates


def _stock_source(session: Session) -> Source:
    topic = Topic(name="股票", slug="stocks", sort_order=1, enabled=True)
    session.add(topic)
    session.flush()
    source = Source(topic_id=topic.id, site="tonghuashun", name="同花顺", entry_url="https://example.com", enabled=True)
    session.add(source)
    session.flush()
    return source


def test_select_item_candidates_skips_short_content(client) -> None:
    session = next(client.app.dependency_overrides[get_session]())
    source = _stock_source(session)
    raw = RawItem(
        source_id=source.id,
        external_id="short",
        url="https://example.com/1",
        title="短",
        body="很短",
        published_at=datetime.utcnow(),
        metrics_json={},
        content_hash="short-hash",
    )
    session.add(raw)
    session.commit()

    assert select_item_candidates(session, source.topic_id, [raw], limit=50) == []


def test_select_item_candidates_skips_existing_enrichment(client) -> None:
    session = next(client.app.dependency_overrides[get_session]())
    source = _stock_source(session)
    raw = RawItem(
        source_id=source.id,
        external_id="ok",
        url="https://example.com/ok",
        title="新能源公告密集发布",
        body="新能源板块相关公司公告密集发布，市场关注度提升。",
        published_at=datetime.utcnow(),
        metrics_json={},
        content_hash="ok-hash",
    )
    session.add(raw)
    session.flush()
    session.add(AIItemEnrichment(topic_id=source.topic_id, raw_item_id=raw.id, status="generated"))
    session.commit()

    assert select_item_candidates(session, source.topic_id, [raw], limit=50) == []


def test_select_item_candidates_uses_24_hour_window(client) -> None:
    session = next(client.app.dependency_overrides[get_session]())
    source = _stock_source(session)
    old = RawItem(
        source_id=source.id,
        external_id="old",
        url="https://example.com/old",
        title="旧公告内容达到长度",
        body="这是一条超过长度下限但已经超过二十四小时的股票资讯内容。",
        published_at=datetime.utcnow() - timedelta(hours=25),
        metrics_json={},
        content_hash="old-hash",
    )
    recent = RawItem(
        source_id=source.id,
        external_id="recent",
        url="https://example.com/recent",
        title="近期公告内容达到长度",
        body="这是一条超过长度下限并且仍在二十四小时窗口内的股票资讯内容。",
        published_at=datetime.utcnow(),
        metrics_json={},
        content_hash="recent-hash",
    )
    session.add_all([old, recent])
    session.commit()

    candidates = select_item_candidates(session, source.topic_id, [old, recent], limit=50)
    assert [item.external_id for item in candidates] == ["recent"]
