from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.entities import AppSetting
from app.services.admin_bootstrap import (
    BOOTSTRAP_COMPLETED_KEY,
    LEGACY_PASSWORD_KEY,
)
from app.services.auth_service import create_user
from app.services.settings import set_plain_setting
from scripts.init_db import main, reconcile_bootstrap_state


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
