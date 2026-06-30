from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import PageBlock, Source, Topic


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


@dataclass(frozen=True)
class BuiltinPageBlock:
    page_route: str
    title: str
    source_type: str
    display_style: str
    display_count: int
    sort_order: int
    col_span: int
    row_span: int
    grid_x: int
    grid_y: int


BUILTIN_TOPICS = (
    BuiltinTopic("股票", "stocks", 10),
    BuiltinTopic("AI", "ai", 20),
    BuiltinTopic("足球", "football", 30),
    BuiltinTopic("游戏", "games", 40),
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
    BuiltinSource("ai", "github_skills", "GitHub-Skills 排行", "github_skills://ranking", 1440, enabled=False),
    BuiltinSource("games", "steam", "Steam-热门游戏榜", "steam://top_sellers", 30),
    BuiltinSource("games", "steam", "Steam-在线热玩榜", "steam://most_played", 30),
    BuiltinSource("games", "steam", "Steam-打折促销", "steam://specials", 60),
    BuiltinSource("games", "steam", "Steam-新游动态", "steam://new_releases", 60),
)

BUILTIN_PAGE_BLOCKS = (
    BuiltinPageBlock("/topics/games", "热门游戏榜", "game_top_sellers", "game-ranking", 10, 10, 2, 2, 0, 0),
    BuiltinPageBlock("/topics/games", "在线热玩榜", "game_most_played", "game-ranking", 10, 15, 2, 2, 2, 0),
    BuiltinPageBlock("/topics/games", "打折促销", "game_specials", "game-deal", 9, 20, 2, 2, 0, 2),
    BuiltinPageBlock("/topics/games", "新游动态", "game_new_releases", "game-release", 10, 30, 2, 1, 2, 2),
)


def _rects_overlap(a: PageBlock, *, x: int, y: int, width: int, height: int) -> bool:
    return not (
        x + width <= a.grid_x
        or a.grid_x + a.col_span <= x
        or y + height <= a.grid_y
        or a.grid_y + a.row_span <= y
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

    for definition in BUILTIN_PAGE_BLOCKS:
        for status in ("draft", "published"):
            existing = session.scalar(
                select(PageBlock)
                .where(
                    PageBlock.page_route == definition.page_route,
                    PageBlock.source_type == definition.source_type,
                    PageBlock.status == status,
                )
                .limit(1)
            )
            if existing is not None:
                if (
                    definition.source_type == "game_most_played"
                    and existing.title in {"热门游戏榜", "Steam 在线热门榜"}
                ):
                    existing.title = definition.title
                continue
            grid_x = definition.grid_x
            grid_y = definition.grid_y
            existing_blocks = session.scalars(
                select(PageBlock).where(
                    PageBlock.page_route == definition.page_route,
                    PageBlock.status == status,
                )
            ).all()
            while any(
                _rects_overlap(block, x=grid_x, y=grid_y, width=definition.col_span, height=definition.row_span)
                for block in existing_blocks
            ):
                grid_y += 1
            session.add(
                PageBlock(
                    page_route=definition.page_route,
                    title=definition.title,
                    sort_order=definition.sort_order,
                    source_type=definition.source_type,
                    source_config={},
                    display_style=definition.display_style,
                    display_count=definition.display_count,
                    sort_by="rank",
                    enabled=True,
                    col_span=definition.col_span,
                    row_span=definition.row_span,
                    grid_x=grid_x,
                    grid_y=grid_y,
                    status=status,
                )
            )

    session.flush()
