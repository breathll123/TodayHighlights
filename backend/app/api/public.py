from hashlib import sha256
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.url_security import UnsafeURLError, is_safe_url, safe_get
from app.models.entities import AITopicSummary, Highlight, MediaAsset, Topic
from app.schemas.public import AITopicSummaryItemRead, AITopicSummaryRead, HighlightRead, TopicRead
from app.services.adapters.eastmoney import fetch_index_trends
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


@router.get("/topics/{slug}/ai-summary")
def get_topic_ai_summary(slug: str, session: Session = Depends(get_session)) -> AITopicSummaryRead:
    topic = session.scalar(select(Topic).where(Topic.slug == slug, Topic.enabled.is_(True)))
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    summary = session.scalar(
        select(AITopicSummary)
        .where(AITopicSummary.topic_id == topic.id, AITopicSummary.status == "generated")
        .order_by(AITopicSummary.summary_date.desc(), AITopicSummary.version.desc())
        .limit(1)
    )
    if summary is None:
        raise HTTPException(status_code=404, detail="No AI summary available")

    return AITopicSummaryRead(
        title=summary.title,
        version=summary.version,
        generated_at=summary.generated_at,
        items=[AITopicSummaryItemRead(**item) for item in summary.items_json],
    )


@router.get("/market-indices")
def get_market_indices() -> list[dict]:
    """6 大指数实时快照 + 当日分时趋势"""
    indices = fetch_index_trends({}, 6)
    if not indices:
        return []
    return [
        {
            "code": idx.get("symbols", [""])[0] if idx.get("symbols") else "",
            "name": idx.get("title", ""),
            "current": idx.get("current", 0),
            "change_pct": idx.get("percent", 0),
            "change_amount": idx.get("change_amount", 0),
            "volume": idx.get("volume", 0),
            "turnover": idx.get("turnover", 0),
            "url": idx.get("url", ""),
            "trend": idx.get("trend"),
        }
        for idx in indices
    ]


@router.get("/media/{url_hash}")
def get_cached_media(url_hash: str, session: Session = Depends(get_session)):
    asset = session.scalar(
        select(MediaAsset).where(MediaAsset.url_hash == url_hash, MediaAsset.status == "cached")
    )
    if asset is None or not asset.local_path or not Path(asset.local_path).exists():
        raise HTTPException(status_code=404, detail="Media not found")
    return FileResponse(asset.local_path, media_type=asset.content_type or "application/octet-stream")


# follow_redirects=False: 重定向由 safe_get() 逐跳校验，杜绝"公网 URL 302 跳内网"绕过
_IMAGE_CLIENT = httpx.Client(
    timeout=10,
    follow_redirects=False,
    headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.qiumiwu.com/"},
)

# 单张代理图片的最大字节数，防止超大响应耗尽内存/磁盘
_MAX_IMAGE_BYTES = 10 * 1024 * 1024

# Disk cache for proxied images
_IMG_CACHE_DIR = Path("/tmp/today-highlights-img-cache")
_IMG_CACHE_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/proxy/image")
def proxy_image(url: str = Query(...)):
    """Proxy third-party images with local disk cache.

    SSRF 防护：仅允许解析到公网 IP 的 http(s) 地址；重定向逐跳校验。
    """
    if not is_safe_url(url):
        raise HTTPException(status_code=403, detail="Blocked: target is not a public http(s) URL")

    # Disk cache: hash URL → local file
    cache_key = sha256(url.encode()).hexdigest()[:24]
    cache_file = _IMG_CACHE_DIR / cache_key

    if cache_file.exists() and cache_file.stat().st_size > 0:
        return FileResponse(cache_file, media_type="image/png")

    try:
        resp = safe_get(_IMAGE_CLIENT, url, max_bytes=_MAX_IMAGE_BYTES)
        resp.raise_for_status()
        body = resp.content
        if not body:
            raise ValueError("empty body")
        content_type = resp.headers.get("content-type", "image/png")
        if body[:4] == b"RIFF" and b"WEBP" in body[:12]:
            content_type = "image/webp"

        # Save to disk cache
        cache_file.write_bytes(body)
        return FileResponse(cache_file, media_type=content_type)
    except UnsafeURLError:
        raise HTTPException(status_code=403, detail="Blocked: redirect target is not public")
    except Exception:
        # Return 1x1 transparent PNG (not cached)
        return StreamingResponse(
            iter([b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"]),
            media_type="image/png",
        )
