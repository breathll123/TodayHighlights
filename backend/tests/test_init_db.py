from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.entities import AppSetting, Source, Topic
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
