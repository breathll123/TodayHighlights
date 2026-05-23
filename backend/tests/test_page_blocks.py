from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models.entities import PageBlock


def test_page_block_crud() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        block = PageBlock(
            page_route="/",
            title="今日热股",
            sort_order=0,
            source_type="hot_stocks",
            source_config={"type": 10},
            display_count=5,
        )
        session.add(block)
        session.commit()

        saved = session.query(PageBlock).one()
        assert saved.title == "今日热股"
        assert saved.source_type == "hot_stocks"
        assert saved.source_config == {"type": 10}
        assert saved.enabled is True


def test_page_block_grid_fields() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        block = PageBlock(
            page_route="/", title="测试", source_type="topic",
            source_config={}, block_key="abc-123",
            col_span=2, row_span=1, grid_x=0, grid_y=0, status="draft",
        )
        session.add(block)
        session.commit()
        saved = session.query(PageBlock).one()
        assert saved.block_key == "abc-123"
        assert saved.col_span == 2
        assert saved.status == "draft"
