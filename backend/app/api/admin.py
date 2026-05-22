from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from pydantic import BaseModel

from app.core.config import settings
from app.core.crypto import CryptoService
from app.core.database import get_session
from app.models.entities import CrawlJob, Highlight, PageBlock, Source
from app.schemas.admin import BlockCreate, BlockRead, BlockUpdate, HighlightUpdate, ReorderRequest, SourceCreate, SourceRead
from app.services.content import update_highlight_review
from app.services.jobs import run_crawl_job
from app.services.settings import get_plain_setting, get_secret_setting, set_plain_setting, set_secret_setting

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


@router.post("/sources/{source_id}/crawl")
def trigger_crawl(source_id: int, session: Session = Depends(get_session)) -> dict:
    job = run_crawl_job(session, source_id, "manual")
    return {"id": job.id, "status": job.status, "items_found": job.items_found, "items_saved": job.items_saved}


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


class ModelSettingsWrite(BaseModel):
    base_url: str
    api_key: str = ""
    model: str


@router.get("/settings/model")
def read_model_settings(session: Session = Depends(get_session)) -> dict:
    return {
        "base_url": get_plain_setting(session, "llm.base_url"),
        "model": get_plain_setting(session, "llm.model"),
        "has_api_key": bool(get_secret_setting(session, "llm.api_key")),
    }


@router.put("/settings/model")
def write_model_settings(payload: ModelSettingsWrite, session: Session = Depends(get_session)) -> dict:
    set_plain_setting(session, "llm.base_url", payload.base_url)
    set_plain_setting(session, "llm.model", payload.model)
    if payload.api_key:
        set_secret_setting(session, "llm.api_key", payload.api_key)
    session.commit()
    return {"saved": True, "has_api_key": bool(payload.api_key)}


@router.get("/blocks", response_model=list[BlockRead])
def list_blocks(session: Session = Depends(get_session)) -> list[PageBlock]:
    return list(session.scalars(select(PageBlock).order_by(PageBlock.page_route, PageBlock.sort_order)))


@router.post("/blocks", response_model=BlockRead)
def create_block(payload: BlockCreate, session: Session = Depends(get_session)) -> PageBlock:
    block = PageBlock(**payload.model_dump())
    session.add(block)
    session.commit()
    session.refresh(block)
    return block


@router.put("/blocks/{block_id}", response_model=BlockRead)
def update_block(block_id: int, payload: BlockUpdate, session: Session = Depends(get_session)) -> PageBlock:
    block = session.get(PageBlock, block_id)
    if block is None:
        raise HTTPException(status_code=404, detail="Block not found")
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(block, key, value)
    session.commit()
    session.refresh(block)
    return block


@router.delete("/blocks/{block_id}")
def delete_block(block_id: int, session: Session = Depends(get_session)) -> dict:
    block = session.get(PageBlock, block_id)
    if block is None:
        return {"deleted": False, "reason": "not found"}
    session.delete(block)
    session.commit()
    return {"deleted": True}


@router.patch("/blocks/reorder")
def reorder_blocks(payload: ReorderRequest, session: Session = Depends(get_session)) -> dict:
    for item in payload.items:
        block = session.get(PageBlock, item["id"])
        if block:
            block.sort_order = item["sort_order"]
    session.commit()
    return {"updated": True}
