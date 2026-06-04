from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.api import admin, public
from app.core.auth import seed_default_password
from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.core.scheduler import create_scheduler
from app.models.entities import Topic


def _seed_defaults() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        existing = session.scalar(select(Topic).where(Topic.slug == "stocks"))
        if existing is None:
            session.add(Topic(name="股票", slug="stocks", sort_order=1, enabled=True))
            session.commit()
        seed_default_password(session)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    try:
        _seed_defaults()
    except Exception:
        pass  # MySQL not available (e.g. during testing)
    if settings.scheduler_enabled:
        scheduler = create_scheduler()
        scheduler.start()
        _app.state.scheduler = scheduler
    yield
    scheduler = getattr(_app.state, "scheduler", None)
    if scheduler is not None:
        scheduler.shutdown(wait=False)
    from app.services.blocks import shutdown_executor
    shutdown_executor()
    from app.core.cache import shutdown_swr_executor
    shutdown_swr_executor()


app = FastAPI(title="Daily Highlights API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(public.router)
app.include_router(admin.auth_router)
app.include_router(admin.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
