from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, ai, artificial_analysis_admin, auth, public
from app.core.cache import cache_backend_status, initialize_cache, shutdown_cache
from app.core.config import settings
from app.core.logging import initialize_logging, shutdown_logging
from app.core.request_logging import install_request_logging
from app.core.scheduler import create_scheduler


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    initialize_logging()
    initialize_cache()
    if settings.scheduler_enabled:
        scheduler = create_scheduler()
        scheduler.start()
        _app.state.scheduler = scheduler
    try:
        yield
    finally:
        scheduler = getattr(_app.state, "scheduler", None)
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        from app.services.blocks import shutdown_executor
        shutdown_executor()
        shutdown_cache()
        shutdown_logging()


app = FastAPI(title="今日看点 API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Install request logging (access/error middleware)
excluded = set(p.strip() for p in settings.log_access_exclude_paths.split(",") if p.strip())
install_request_logging(
    app,
    slow_request_ms=settings.log_slow_request_ms,
    excluded_paths=excluded,
    trust_proxy_headers=settings.log_trust_proxy_headers,
)

app.include_router(auth.router)
app.include_router(public.router)
app.include_router(ai.router)
app.include_router(admin.router)
app.include_router(artificial_analysis_admin.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "cache": cache_backend_status()}
