from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI

from app.api import admin, public
from app.core.config import settings
from app.core.scheduler import create_scheduler


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    if settings.scheduler_enabled:
        scheduler = create_scheduler()
        scheduler.start()
        _app.state.scheduler = scheduler
    yield
    scheduler = getattr(_app.state, "scheduler", None)
    if scheduler is not None:
        scheduler.shutdown(wait=False)


app = FastAPI(title="Daily Highlights API", lifespan=lifespan)
app.include_router(public.router)
app.include_router(admin.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
