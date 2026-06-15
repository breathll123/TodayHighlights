from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.entities import PageBlock, RawItem, Source, Topic
from app.services.blocks import resolve_block_data


def test_longhu_block_only_returns_latest_datacenter_records() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as session:
        topic = Topic(name="股票", slug="stocks")
        source = Source(
            topic=topic,
            site="eastmoney",
            name="东方财富-龙虎榜",
            entry_url="eastmoney://longhu",
        )
        session.add(source)
        session.flush()

        session.add_all(
            [
                RawItem(
                    source_id=source.id,
                    external_id="em_longhu_2026-06-15_000001",
                    url="https://example.com/legacy",
                    title="旧接口错误数据",
                    body="旧接口内容",
                    published_at=datetime(2026, 6, 15, 15, 0),
                    metrics_json={"symbol": "000001", "net_buy": 999999999},
                    content_hash="legacy",
                ),
                RawItem(
                    source_id=source.id,
                    external_id="lhb_002203_2026-06-12 00:00:00",
                    url="https://example.com/old-lhb-format",
                    title="旧版 LHB 格式数据",
                    body="旧版数据的写入时间晚于交易时间",
                    published_at=datetime(2026, 6, 15, 2, 48, 35),
                    metrics_json={"symbol": "002203", "net_buy": 1999999999},
                    content_hash="old-lhb-format",
                ),
                RawItem(
                    source_id=source.id,
                    external_id="lhb_2026-06-14_100",
                    url="https://example.com/previous",
                    title="上一交易日数据",
                    body="上一交易日内容",
                    published_at=datetime(2026, 6, 14),
                    metrics_json={"symbol": "000002", "net_buy": 888888888},
                    content_hash="previous",
                ),
                RawItem(
                    source_id=source.id,
                    external_id="lhb_2026-06-15_101",
                    url="https://example.com/current",
                    title="最新正确数据",
                    body="最新交易日内容",
                    published_at=datetime(2026, 6, 15),
                    metrics_json={"symbol": "301526", "net_buy": 268777357, "percent": 20.007},
                    content_hash="current",
                ),
                RawItem(
                    source_id=source.id,
                    external_id="lhb_2026-06-15_102",
                    url="https://example.com/top",
                    title="净额最高数据",
                    body="最新交易日净额最高",
                    published_at=datetime(2026, 6, 15),
                    metrics_json={
                        "symbol": "300620",
                        "net_buy": 1537055379,
                        "percent": 19.999,
                        "reason": "日涨幅达到15%的前5只证券",
                    },
                    content_hash="top",
                ),
                RawItem(
                    source_id=source.id,
                    external_id="lhbX2026-06-16_legacy",
                    url="https://example.com/similar-prefix",
                    title="相似前缀错误数据",
                    body="不能算作数据中心记录",
                    published_at=datetime(2026, 6, 16),
                    metrics_json={"symbol": "000003", "net_buy": 9999999999},
                    content_hash="similar-prefix",
                ),
            ]
        )
        block = PageBlock(
            page_route="/topics/stocks",
            title="龙虎榜",
            source_type="eastmoney_longhu",
            source_config={},
            display_count=1,
            status="published",
        )
        session.add(block)
        session.commit()

        result = resolve_block_data(session, block)

    assert [item["title"] for item in result] == ["净额最高数据"]
    assert result[0]["net_amount"] == 1537055379
    assert result[0]["reason"] == "日涨幅达到15%的前5只证券"
