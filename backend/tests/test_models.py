from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models.entities import Highlight, RawItem, Source, Topic


def test_topic_source_raw_item_highlight_relationships() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        topic = Topic(name="股票", slug="stocks", sort_order=1, enabled=True)
        source = Source(topic=topic, site="xueqiu", name="雪球自选", entry_url="https://xueqiu.com", enabled=True)
        raw = RawItem(source=source, external_id="100", url="https://xueqiu.com/100", title="原文", body="正文", content_hash="abc123")
        highlight = Highlight(topic=topic, raw_item=raw, title="看点", summary="摘要", score=80)
        session.add(highlight)
        session.commit()

        saved = session.query(Highlight).one()
        assert saved.topic.slug == "stocks"
        assert saved.raw_item.source.site == "xueqiu"
