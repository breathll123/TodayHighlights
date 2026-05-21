from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.models.entities import Source, Topic
from app.services.content import save_raw_items
from app.sources.base import RawItemDraft


def test_save_raw_items_deduplicates_by_external_id() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as session:
        topic = Topic(name="股票", slug="stocks")
        source = Source(topic=topic, site="xueqiu", name="雪球", entry_url="https://xueqiu.com")
        session.add(source)
        session.commit()

        draft = RawItemDraft(
            external_id="123",
            url="https://xueqiu.com/123",
            author="作者",
            title="标题",
            body="正文",
            published_at=None,
            metrics={"fav_count": 1},
            content_hash="hash-123",
        )

        first = save_raw_items(session, source.id, [draft])
        second = save_raw_items(session, source.id, [draft])

        assert len(first) == 1
        assert second == []
