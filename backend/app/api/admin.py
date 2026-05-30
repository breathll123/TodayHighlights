from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, joinedload

from pydantic import BaseModel

from fastapi import Request

from app.core.auth import create_admin_token, verify_admin
from app.core.config import settings
from app.core.crypto import CryptoService
from app.core.database import get_session
from app.models.entities import CrawlJob, Highlight, PageBlock, Source, Topic
from app.schemas.admin import BlockCreate, BlockRead, BlockUpdate, HighlightUpdate, ReorderRequest, SourceCreate, SourceRead, SourceUpdate
from app.services.content import update_highlight_review
from app.services.jobs import run_crawl_job
from app.services.settings import get_plain_setting, get_secret_setting, set_plain_setting, set_secret_setting

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(verify_admin)])
auth_router = APIRouter(prefix="/api/admin", tags=["auth"])


@router.get("/sources")
def list_sources(type: str | None = None, session: Session = Depends(get_session)) -> list[dict]:
    if type == "raw":
        sources = session.scalars(
            select(Source).where(Source.site.in_(["xueqiu", "eastmoney", "tonghuashun"])).order_by(Source.id)
        ).all()
        return [{"id": s.id, "name": f"[{s.site}] {s.name}"} for s in sources]

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


@router.put("/sources/{source_id}", response_model=SourceRead)
def update_source(source_id: int, payload: SourceUpdate, session: Session = Depends(get_session)) -> dict:
    source = session.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    crypto = CryptoService(settings.app_secret_key)
    if payload.name is not None:
        source.name = payload.name
    if payload.entry_url is not None:
        source.entry_url = payload.entry_url
    if payload.cookie is not None and payload.cookie != "":
        source.cookie_encrypted = crypto.encrypt(payload.cookie)
    if payload.enabled is not None:
        source.enabled = payload.enabled
    if payload.crawl_interval_minutes is not None:
        source.crawl_interval_minutes = payload.crawl_interval_minutes
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
def list_jobs(page: int = 1, page_size: int = 20, session: Session = Depends(get_session)) -> dict:
    total = session.scalar(select(func.count()).select_from(CrawlJob))
    jobs = session.scalars(
        select(CrawlJob).options(joinedload(CrawlJob.source)).order_by(CrawlJob.created_at.desc())
        .limit(page_size).offset((page - 1) * page_size)
    ).all()
    return {
        "total": total or 0,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": job.id,
                "source_id": job.source_id,
                "source_name": job.source.name if job.source else str(job.source_id),
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
        ],
    }


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


class TopicWrite(BaseModel):
    name: str
    slug: str
    sort_order: int = 0
    enabled: bool = True


@router.get("/topics")
def list_admin_topics(session: Session = Depends(get_session)) -> list[dict]:
    topics = session.scalars(select(Topic).order_by(Topic.sort_order)).all()
    return [{"id": t.id, "name": t.name, "slug": t.slug, "sort_order": t.sort_order, "enabled": t.enabled} for t in topics]


@router.post("/topics")
def create_topic(payload: TopicWrite, session: Session = Depends(get_session)) -> dict:
    t = Topic(name=payload.name, slug=payload.slug, sort_order=payload.sort_order, enabled=payload.enabled)
    session.add(t)
    session.commit()
    session.refresh(t)
    return {"id": t.id, "name": t.name, "slug": t.slug, "sort_order": t.sort_order, "enabled": t.enabled}


@router.put("/topics/{topic_id}")
def update_topic(topic_id: int, payload: TopicWrite, session: Session = Depends(get_session)) -> dict:
    t = session.get(Topic, topic_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    t.name = payload.name
    t.slug = payload.slug
    t.sort_order = payload.sort_order
    t.enabled = payload.enabled
    session.commit()
    session.refresh(t)
    return {"id": t.id, "name": t.name, "slug": t.slug, "sort_order": t.sort_order, "enabled": t.enabled}


@router.delete("/topics/{topic_id}")
def delete_topic(topic_id: int, session: Session = Depends(get_session)) -> dict:
    t = session.get(Topic, topic_id)
    if t is None:
        return {"deleted": False, "reason": "not found"}
    session.delete(t)
    session.commit()
    return {"deleted": True}


class LoginRequest(BaseModel):
    password: str


@router.post("/pages/{route:path}/publish")
def publish_page(route: str, session: Session = Depends(get_session)) -> dict:
    route = "/" + route if not route.startswith("/") else route

    session.execute(
        delete(PageBlock).where(
            PageBlock.page_route == route,
            PageBlock.status == "published"
        )
    )

    drafts = session.scalars(
        select(PageBlock).where(
            PageBlock.page_route == route,
            PageBlock.status == "draft"
        )
    ).all()

    count = 0
    for d in drafts:
        published = PageBlock(
            block_key=d.block_key,
            page_route=d.page_route,
            title=d.title,
            sort_order=d.sort_order,
            source_type=d.source_type,
            source_config=d.source_config,
            display_style=d.display_style,
            display_count=d.display_count,
            sort_by=d.sort_by,
            col_span=d.col_span,
            row_span=d.row_span,
            grid_x=d.grid_x,
            grid_y=d.grid_y,
            status="published",
            enabled=True,
        )
        session.add(published)
        count += 1

    session.commit()
    return {"published": True, "blocks": count}


@auth_router.post("/login")
def login(payload: LoginRequest, session: Session = Depends(get_session)) -> dict:
    token = create_admin_token(payload.password, session)
    return {"token": token}
