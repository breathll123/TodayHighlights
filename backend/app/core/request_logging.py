from __future__ import annotations

import logging
import re
import secrets
import time
from typing import TYPE_CHECKING

from app.core.logging import bind_log_context, log_event

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger("today_highlights.http")

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{8,128}$")


def valid_request_id(value: str | None) -> bool:
    return bool(value and _REQUEST_ID_PATTERN.fullmatch(value))


def new_request_id() -> str:
    return secrets.token_hex(16)


def install_request_logging(
    app: FastAPI,
    *,
    slow_request_ms: int,
    excluded_paths: set[str],
    trust_proxy_headers: bool,
) -> None:
    from fastapi import Request
    from fastapi.responses import JSONResponse

    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID")
        if not valid_request_id(request_id):
            request_id = new_request_id()
        request.state.request_id = request_id
        started = time.perf_counter()
        status_code = 500

        with bind_log_context(request_id=request_id):
            try:
                response = await call_next(request)
                status_code = response.status_code
            except Exception:
                log_event(
                    logger,
                    channel="error",
                    event="unhandled_http_exception",
                    level=logging.ERROR,
                    exc_info=True,
                    method=request.method,
                    path=request.url.path,
                )
                response = JSONResponse(
                    status_code=500,
                    content={"detail": "Internal server error", "request_id": request_id},
                )

            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            response.headers["X-Request-ID"] = request_id
            if request.url.path not in excluded_paths:
                query_keys = ",".join(sorted(request.query_params.keys())) or "-"
                client_ip = request.client.host if request.client else "-"
                if trust_proxy_headers:
                    forwarded = request.headers.get("X-Forwarded-For", "")
                    if forwarded:
                        client_ip = forwarded.split(",", 1)[0].strip()
                log_event(
                    logger,
                    channel="access",
                    event="http_request_completed",
                    method=request.method,
                    path=request.url.path,
                    query_keys=query_keys,
                    status=status_code,
                    duration_ms=duration_ms,
                    client_ip=client_ip,
                    user_id=getattr(request.state, "user_id", "-"),
                    slow=duration_ms >= slow_request_ms,
                )
            return response
