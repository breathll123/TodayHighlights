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


# Allowed image proxy domains
_IMAGE_PROXY_DOMAINS = {"file.qiumiwu.com", "img.qiumiwu.com", "sd.qunliao.info", "bdimg.qunliao.info"}

_IMAGE_CLIENT = httpx.Client(timeout=10, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.qiumiwu.com/"})


@router.get("/proxy/image")
def proxy_image(url: str = Query(...)):
    """Proxy third-party images to fix Content-Type mismatches and CORS."""
    domain = urlparse(url).netloc
    if domain not in _IMAGE_PROXY_DOMAINS:
        raise HTTPException(status_code=403, detail=f"Domain not allowed: {domain}")

    try:
        resp = _IMAGE_CLIENT.get(url)
        resp.raise_for_status()
    except Exception:
        raise HTTPException(status_code=502, detail="Failed to fetch image")

    content_type = resp.headers.get("content-type", "image/png")
    # Fix WebP served as PNG
    body = resp.content
    if body[:4] == b"RIFF" and b"WEBP" in body[:12]:
        content_type = "image/webp"

    return StreamingResponse(
        iter([body]),
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )
