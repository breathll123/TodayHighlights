from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, ai, auth, public
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
    from app.services.blocks import shutdown_executor
    shutdown_executor()
    from app.core.cache import shutdown_swr_executor
    shutdown_swr_executor()


app = FastAPI(title="今日看点 API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(public.router)
app.include_router(ai.router)
app.include_router(admin.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
