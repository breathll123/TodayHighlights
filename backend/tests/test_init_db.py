from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.entities import AppSetting, PageBlock, Source, Topic
from app.services.admin_bootstrap import (
    BOOTSTRAP_COMPLETED_KEY,
    LEGACY_PASSWORD_KEY,
)
from app.services.auth_service import create_user
from app.services.settings import set_plain_setting
from scripts.init_db import main, reconcile_bootstrap_state, reconcile_system_catalog


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with TestingSessionLocal() as session:
        yield session


def test_reconcile_marks_existing_real_admin_complete(db_session):
    create_user(db_session, "owner", "", "secret123", role="admin")

    reconcile_bootstrap_state(db_session)

    assert db_session.get(AppSetting, BOOTSTRAP_COMPLETED_KEY) is not None


def test_reconcile_leaves_only_legacy_admin_open(db_session):
    create_user(db_session, "admin", "", "admin123", role="admin")

    reconcile_bootstrap_state(db_session)

    assert db_session.get(AppSetting, BOOTSTRAP_COMPLETED_KEY) is None


def test_reconcile_removes_plaintext_password_setting(db_session):
    set_plain_setting(db_session, LEGACY_PASSWORD_KEY, "admin123")

    reconcile_bootstrap_state(db_session)

    setting = db_session.scalar(
        select(AppSetting).where(AppSetting.key == LEGACY_PASSWORD_KEY)
    )
    assert setting is None


def test_main_runs_migrations_before_reconciliation(db_session):
    events: list[str] = []

    def fake_upgrade(_config, revision):
        assert revision == "head"
        events.append("upgrade")

    def session_factory():
        assert events == ["upgrade"]
        events.append("session")
        return db_session

    exit_code = main(
        upgrade_fn=fake_upgrade,
        session_factory=session_factory,
        output=lambda message: events.append(message),
    )

    assert exit_code == 0
    assert events[:2] == ["upgrade", "session"]
    assert any("浏览器" in event for event in events)


def test_reconcile_system_catalog_normalizes_legacy_stock_topic(db_session):
    db_session.add(Topic(name="A股市场", slug="a-stock", sort_order=0, enabled=True))
    db_session.flush()

    reconcile_system_catalog(db_session)

    topics = db_session.scalars(select(Topic).order_by(Topic.sort_order)).all()
    assert [(topic.name, topic.slug) for topic in topics] == [
        ("股票", "stocks"),
        ("AI", "ai"),
        ("足球", "football"),
        ("游戏", "games"),
    ]


def test_reconcile_system_catalog_seeds_sources_idempotently(db_session):
    reconcile_system_catalog(db_session)
    stock_topic = db_session.scalar(select(Topic).where(Topic.slug == "stocks"))
    existing = db_session.scalar(
        select(Source).where(
            Source.site == "eastmoney",
            Source.entry_url == "eastmoney://indices",
        )
    )
    assert stock_topic is not None
    assert existing is not None

    existing.enabled = False
    existing.crawl_interval_minutes = 99
    db_session.add(
        Source(
            topic_id=stock_topic.id,
            site="eastmoney",
            name="旧涨幅榜",
            entry_url="eastmoney://gainers",
            cookie_encrypted="",
            enabled=True,
            crawl_interval_minutes=5,
        )
    )
    db_session.flush()

    reconcile_system_catalog(db_session)

    matching = db_session.scalars(
        select(Source).where(
            Source.site == "eastmoney",
            Source.entry_url == "eastmoney://indices",
        )
    ).all()
    assert len(matching) == 1
    assert matching[0].topic_id == stock_topic.id
    assert matching[0].enabled is False
    assert matching[0].crawl_interval_minutes == 99
    deprecated = db_session.scalar(
        select(Source).where(Source.entry_url == "eastmoney://gainers")
    )
    assert deprecated is not None
    assert deprecated.enabled is False

    source_keys = {
        (source.site, source.entry_url)
        for source in db_session.scalars(select(Source)).all()
    }
    assert ("eastmoney", "eastmoney://longhu") in source_keys
    assert ("dongqiudi", "dongqiudi://matches") in source_keys
    assert ("qiumiwu", "qiumiwu://matches") in source_keys
    assert ("aihot", "aihot://news") in source_keys
    assert ("steam", "steam://charts_concurrent") in source_keys
    assert ("steam", "steam://most_played") not in source_keys
    assert ("wegame", "wegame://popular_this_week") in source_keys
    assert ("wegame", "wegame://this_week_most_purchase") in source_keys
    assert ("wegame", "wegame://discounts") in source_keys


def test_reconcile_system_catalog_seeds_game_page_blocks_idempotently(db_session):
    reconcile_system_catalog(db_session)

    blocks = db_session.scalars(
        select(PageBlock).where(PageBlock.page_route == "/topics/games")
    ).all()
    assert len(blocks) == 12
    assert {
        (block.title, block.source_type, block.status)
        for block in blocks
    } == {
        ("热门游戏榜", "game_top_sellers", "draft"),
        ("热门游戏榜", "game_top_sellers", "published"),
        ("实时热玩榜", "game_charts_concurrent", "draft"),
        ("实时热玩榜", "game_charts_concurrent", "published"),
        ("打折促销", "game_specials", "draft"),
        ("打折促销", "game_specials", "published"),
        ("新游动态", "game_new_releases", "draft"),
        ("新游动态", "game_new_releases", "published"),
        ("WeGame 最高热度", "game_wegame_popular", "draft"),
        ("WeGame 最高热度", "game_wegame_popular", "published"),
        ("WeGame 本周热销", "game_wegame_weekly_sales", "draft"),
        ("WeGame 本周热销", "game_wegame_weekly_sales", "published"),
    }
    deal_blocks = [block for block in blocks if block.title == "打折促销"]
    assert len(deal_blocks) == 2
    assert all(block.source_config["sources"] == [
        {"source_type": "game_specials", "label": "Steam"},
        {"source_type": "game_wegame_discounts", "label": "WeGame"},
    ] for block in deal_blocks)

    reconcile_system_catalog(db_session)

    assert db_session.scalar(
        select(func.count()).select_from(PageBlock).where(PageBlock.page_route == "/topics/games")
    ) == 12


def test_reconcile_system_catalog_deprecates_steam_most_played(db_session):
    game_topic = Topic(name="游戏", slug="games", sort_order=40, enabled=True)
    db_session.add(game_topic)
    db_session.flush()
    db_session.add(
        Source(
            topic_id=game_topic.id,
            site="steam",
            name="Steam-在线热玩榜",
            entry_url="steam://most_played",
            cookie_encrypted="",
            enabled=True,
            crawl_interval_minutes=30,
        )
    )
    db_session.add_all([
        PageBlock(
            page_route="/topics/games",
            title="在线热玩榜",
            source_type="game_most_played",
            display_style="game-ranking",
            display_count=10,
            sort_by="rank",
            enabled=True,
            col_span=2,
            row_span=2,
            grid_x=0,
            grid_y=0,
            status="draft",
        ),
        PageBlock(
            page_route="/topics/games",
            title="在线热玩榜",
            source_type="game_most_played",
            display_style="game-ranking",
            display_count=10,
            sort_by="rank",
            enabled=True,
            col_span=2,
            row_span=2,
            grid_x=0,
            grid_y=0,
            status="published",
        ),
    ])
    db_session.flush()

    reconcile_system_catalog(db_session)

    source = db_session.scalar(select(Source).where(Source.entry_url == "steam://most_played"))
    assert source is not None
    assert source.enabled is False
    assert db_session.scalar(
        select(func.count()).select_from(PageBlock).where(PageBlock.source_type == "game_most_played")
    ) == 0


def test_reconcile_system_catalog_migrates_legacy_game_discount_blocks(db_session):
    db_session.add(Topic(name="游戏", slug="games", sort_order=40, enabled=True))
    db_session.add_all([
        PageBlock(
            page_route="/topics/games",
            title="打折促销",
            source_type="game_specials",
            source_config={},
            display_style="game-deal",
            display_count=9,
            sort_by="rank",
            enabled=True,
            col_span=4,
            row_span=2,
            grid_x=0,
            grid_y=2,
            status="draft",
        ),
        PageBlock(
            page_route="/topics/games",
            title="WeGame 折扣促销",
            source_type="game_wegame_discounts",
            source_config={},
            display_style="game-ranking",
            display_count=10,
            sort_by="rank",
            enabled=True,
            col_span=2,
            row_span=2,
            grid_x=0,
            grid_y=6,
            status="draft",
        ),
    ])
    db_session.flush()

    reconcile_system_catalog(db_session)

    migrated = db_session.scalar(
        select(PageBlock).where(
            PageBlock.page_route == "/topics/games",
            PageBlock.title == "打折促销",
            PageBlock.status == "draft",
        )
    )
    assert migrated is not None
    assert migrated.source_type == "game_specials"
    assert migrated.display_style == "game-deal"
    assert migrated.source_config["sources"][0]["source_type"] == "game_specials"
    assert migrated.source_config["sources"][1]["source_type"] == "game_wegame_discounts"

    legacy_wegame = db_session.scalar(
        select(PageBlock).where(
            PageBlock.page_route == "/topics/games",
            PageBlock.title == "WeGame 折扣促销",
            PageBlock.status == "draft",
        )
    )
    assert legacy_wegame is None
