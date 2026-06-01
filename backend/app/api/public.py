from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.models.entities import Highlight, Topic
from app.schemas.public import HighlightRead, TopicRead
from app.services.blocks import get_page_blocks

router = APIRouter(prefix="/api/public", tags=["public"])


@router.get("/topics", response_model=list[TopicRead])
def list_topics(session: Session = Depends(get_session)) -> list[Topic]:
    return list(session.scalars(select(Topic).where(Topic.enabled.is_(True)).order_by(Topic.sort_order)))


@router.get("/highlights", response_model=list[HighlightRead])
def list_highlights(session: Session = Depends(get_session)) -> list[Highlight]:
    statement = (
        select(Highlight)
        .where(Highlight.is_hidden.is_(False))
        .order_by(Highlight.is_pinned.desc(), Highlight.score.desc(), Highlight.created_at.desc())
    )
    return list(session.scalars(statement))


@router.get("/pages/{route:path}/blocks")
def page_blocks(route: str, session: Session = Depends(get_session)) -> dict:
    route = "/" + route if not route.startswith("/") else route
    blocks = get_page_blocks(session, route)
    return {"blocks": blocks}


_IMAGE_CLIENT = httpx.Client(timeout=10, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.qiumiwu.com/"})


@router.get("/proxy/image")
def proxy_image(url: str = Query(...)):
    """Proxy third-party images to fix Content-Type mismatches and CORS.

    Domain allowlist is deferred to nginx proxy layer at deployment time.
    Local dev allows all domains."""
    domain = urlparse(url).netloc
    # Only block obviously internal hosts to prevent basic SSRF
    if domain in ("localhost", "127.0.0.1", "::1") or domain.startswith("10.") or domain.startswith("192.168.") or domain.startswith("172.16."):
        raise HTTPException(status_code=403, detail=f"Internal host blocked: {domain}")

    try:
        resp = _IMAGE_CLIENT.get(url)
        resp.raise_for_status()
        body = resp.content
        if not body:
            raise ValueError("empty body")
        content_type = resp.headers.get("content-type", "image/png")
        # Fix WebP served as PNG
        if body[:4] == b"RIFF" and b"WEBP" in body[:12]:
            content_type = "image/webp"
    except Exception:
        # Return 1x1 transparent PNG
        body = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        content_type = "image/png"

    return StreamingResponse(
        iter([body]),
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )
