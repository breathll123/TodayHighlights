from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import CryptoService
from app.core.database import get_session
from app.models.entities import CrawlJob, Highlight, Source
from app.schemas.admin import HighlightUpdate, SourceCreate, SourceRead
from app.services.content import update_highlight_review

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/sources", response_model=list[SourceRead])
def list_sources(session: Session = Depends(get_session)) -> list[dict]:
    sources = session.scalars(select(Source).order_by(Source.id.desc())).all()
    return [
        {
            "id": source.id,
            "topic_id": source.topic_id,
            "site": source.site,
            "name": source.name,
            "entry_url": source.entry_url,
            "enabled": source.enabled,
            "crawl_interval_minutes": source.crawl_interval_minutes,
            "last_crawled_at": source.last_crawled_at,
            "has_cookie": bool(source.cookie_encrypted),
        }
        for source in sources
    ]


@router.post("/sources", response_model=SourceRead)
def create_source(payload: SourceCreate, session: Session = Depends(get_session)) -> dict:
    crypto = CryptoService(settings.app_secret_key)
    source = Source(
        topic_id=payload.topic_id,
        site=payload.site,
        name=payload.name,
        entry_url=payload.entry_url,
        cookie_encrypted=crypto.encrypt(payload.cookie),
        enabled=payload.enabled,
        crawl_interval_minutes=payload.crawl_interval_minutes,
    )
    session.add(source)
    session.commit()
    session.refresh(source)
    return {
        "id": source.id,
        "topic_id": source.topic_id,
        "site": source.site,
        "name": source.name,
        "entry_url": source.entry_url,
        "enabled": source.enabled,
        "crawl_interval_minutes": source.crawl_interval_minutes,
        "last_crawled_at": source.last_crawled_at,
        "has_cookie": bool(source.cookie_encrypted),
    }


@router.get("/jobs")
def list_jobs(session: Session = Depends(get_session)) -> list[dict]:
    jobs = session.scalars(select(CrawlJob).order_by(CrawlJob.created_at.desc()).limit(50)).all()
    return [
        {
            "id": job.id,
            "source_id": job.source_id,
            "trigger_type": job.trigger_type,
            "status": job.status,
            "items_found": job.items_found,
            "items_saved": job.items_saved,
            "error_message": job.error_message,
            "log_excerpt": job.log_excerpt,
            "started_at": job.started_at,
            "finished_at": job.finished_at,
        }
        for job in jobs
    ]


@router.patch("/highlights/{highlight_id}")
def update_highlight(highlight_id: int, payload: HighlightUpdate, session: Session = Depends(get_session)) -> dict:
    highlight = update_highlight_review(
        session,
        highlight_id,
        title=payload.title,
        summary=payload.summary,
        is_pinned=payload.is_pinned,
        is_hidden=payload.is_hidden,
    )
    session.commit()
    return {"id": highlight.id, "review_status": highlight.review_status}
