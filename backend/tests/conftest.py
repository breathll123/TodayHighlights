from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import verify_admin
from app.core.database import Base, get_session
from app.main import app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    app.dependency_overrides.clear()

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    Base.metadata.create_all(engine)

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
