from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Source, Topic


@dataclass(frozen=True)
class BuiltinTopic:
    name: str
    slug: str
    sort_order: int


@dataclass(frozen=True)
class BuiltinSource:
    topic_slug: str
    site: str
    name: str
    entry_url: str
    crawl_interval_minutes: int
    enabled: bool = True


BUILTIN_TOPICS = (
    BuiltinTopic("股票", "stocks", 10),
    BuiltinTopic("AI", "ai", 20),
    BuiltinTopic("足球", "football", 30),
)

BUILTIN_SOURCES = (
    BuiltinSource(
        "stocks",
        "xueqiu",
        "雪球自选",
        "https://xueqiu.com/v4/statuses/public_timeline_by_category.json",
        10,
        enabled=False,
    ),
    BuiltinSource("stocks", "eastmoney", "东方财富-概念板块", "eastmoney://sectors", 5),
    BuiltinSource("stocks", "eastmoney", "东方财富-行业板块", "eastmoney://industry", 5),
    BuiltinSource("stocks", "eastmoney", "东方财富-主力资金流入", "eastmoney://capital_flow", 5),
    BuiltinSource("stocks", "eastmoney", "东方财富-指数行情", "eastmoney://indices", 5),
    BuiltinSource("stocks", "eastmoney", "东方财富-龙虎榜", "eastmoney://longhu", 5),
    BuiltinSource("stocks", "tonghuashun", "同花顺-财经快讯", "tonghuashun://news", 1),
    BuiltinSource("football", "dongqiudi", "懂球帝-比赛数据", "dongqiudi://matches", 1),
    BuiltinSource("football", "qiumiwu", "球迷屋-比赛数据", "qiumiwu://matches", 2),
    BuiltinSource("ai", "aihot", "AI HOT-资讯快讯", "aihot://news", 2),
)


def reconcile_system_catalog(session: Session) -> None:
    legacy_stock = session.scalar(select(Topic).where(Topic.slug == "a-stock"))
    stock_topic = session.scalar(select(Topic).where(Topic.slug == "stocks"))
    if legacy_stock is not None and stock_topic is None:
        legacy_stock.name = "股票"
        legacy_stock.slug = "stocks"
        legacy_stock.sort_order = 10
        stock_topic = legacy_stock

    topics_by_slug: dict[str, Topic] = {}
    for definition in BUILTIN_TOPICS:
        topic = stock_topic if definition.slug == "stocks" else None
        if topic is None:
            topic = session.scalar(select(Topic).where(Topic.slug == definition.slug))
        if topic is None:
            topic = Topic(
                name=definition.name,
                slug=definition.slug,
                sort_order=definition.sort_order,
                enabled=True,
            )
            session.add(topic)
            session.flush()
        topics_by_slug[definition.slug] = topic

    for definition in BUILTIN_SOURCES:
        source = session.scalar(
            select(Source).where(
                Source.site == definition.site,
                Source.entry_url == definition.entry_url,
            )
        )
        topic = topics_by_slug[definition.topic_slug]
        if source is None:
            session.add(
                Source(
                    topic_id=topic.id,
                    site=definition.site,
                    name=definition.name,
                    entry_url=definition.entry_url,
                    cookie_encrypted="",
                    enabled=definition.enabled,
                    crawl_interval_minutes=definition.crawl_interval_minutes,
                    enable_highlight=False,
                )
            )
        elif source.topic_id != topic.id:
            source.topic_id = topic.id

    deprecated_gainers = session.scalar(
        select(Source).where(
            Source.site == "eastmoney",
            Source.entry_url == "eastmoney://gainers",
        )
    )
    if deprecated_gainers is not None:
        deprecated_gainers.enabled = False

    session.flush()
