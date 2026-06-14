from __future__ import annotations

import logging
import re
import secrets
import time
from typing import TYPE_CHECKING

from app.core.logging import bind_log_context, log_event
from app.core.logging import format_duration

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger("today_highlights.http")

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{8,128}$")


def valid_request_id(value: str | None) -> bool:
    return bool(value and _REQUEST_ID_PATTERN.fullmatch(value))


def new_request_id() -> str:
    return secrets.token_hex(16)


def normalize_log_path(path: str) -> str:
    return re.sub(r"/{2,}", "/", path)


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
                    event="http.unhandled",
                    level=logging.ERROR,
                    exc_info=True,
                    method=request.method,
                    path=normalize_log_path(request.url.path),
                    username=getattr(request.state, "username", "-"),
                    user_id=getattr(request.state, "user_id", "-"),
                    request=request_id[:8],
                    error_type="UnhandledException",
                )
                response = JSONResponse(
                    status_code=500,
                    content={"detail": "Internal server error", "request_id": request_id},
                )
        elapsed = time.perf_counter() - started
        duration_ms = round(elapsed * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        if request.url.path not in excluded_paths:
            query_keys = ",".join(sorted(request.query_params.keys())) or "-"
            client_ip = request.client.host if request.client else "-"
            if trust_proxy_headers:
                forwarded = request.headers.get("X-Forwarded-For", "")
                if forwarded:
                    client_ip = forwarded.split(",", 1)[0].strip()
            response_length = response.headers.get("content-length", "")
            log_event(
                logger,
                channel="access",
                category="access",
                event="http.completed",
                method=request.method,
                path=normalize_log_path(request.url.path),
                query_keys=query_keys,
                status=status_code,
                duration=format_duration(elapsed),
                client_ip=client_ip,
                username=getattr(request.state, "username", "-"),
                user_id=getattr(request.state, "user_id", "-"),
                response_bytes=int(response_length) if response_length.isdigit() else "-",
                request=request_id[:8],
                slow=duration_ms >= slow_request_ms,
            )
        return response
