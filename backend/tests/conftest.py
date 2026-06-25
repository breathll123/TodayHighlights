import os
import tempfile
from pathlib import Path

os.environ.setdefault("REDIS_ENABLED", "false")
# 测试不连真实 MySQL：禁用启动时的遗留任务回收（reconcile 走真实 SessionLocal）。
os.environ.setdefault("CRAWL_RECONCILE_ON_STARTUP", "false")

_TEST_LOG_DIR = Path(tempfile.gettempdir()) / "today-highlights-test-logs"
os.environ.setdefault("LOG_DIR", str(_TEST_LOG_DIR))
os.environ.setdefault("LOG_CONSOLE_ENABLED", "false")
os.environ.setdefault("LOG_RETENTION_DAYS", "1")

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import verify_admin
from app.core.cache import (
    MemoryCacheBackend,
    configure_cache_backend_for_tests,
    reset_cache_backend_for_tests,
)
from app.core.database import Base, get_session
from app.main import app


@pytest.fixture(autouse=True)
def _init_cache_backend() -> Generator[None, None, None]:
    """Ensure every test has a memory cache backend available."""
    backend = MemoryCacheBackend(maxsize=256)
    configure_cache_backend_for_tests(backend)
    yield
    reset_cache_backend_for_tests()


@pytest.fixture
def engine():
    # 创建共享的内存 SQLite engine，供测试客户端与测试用例共用
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    yield eng


@pytest.fixture
def db_session(engine) -> Generator:
    # 创建共享的 SQLAlchemy 会话，便于在测试代码中直接插入和校验数据
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(engine) -> Generator[TestClient, None, None]:
    # 创建 FastAPI TestClient 并覆盖数据库依赖，使其指向共享的 engine
    app.dependency_overrides.clear()

    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_session():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    def override_verify_admin():
        return True

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[verify_admin] = override_verify_admin

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
