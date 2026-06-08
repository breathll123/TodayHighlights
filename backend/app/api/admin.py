from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session, joinedload

from pydantic import BaseModel

from fastapi import Request

from app.core.auth import create_admin_token, get_current_user, verify_admin
from app.core.config import settings
from app.core.crypto import CryptoService
from app.core.database import get_session
from app.models.entities import AIGenerationJob, AIBlockAnalysis, AIPromptTemplate, AITokenUsage, CrawlJob, Highlight, PageBlock, Source, Topic, User
from app.schemas.admin import AIJobListResponse, AIJobRead, AIModelConfigWrite, BlockCreate, BlockRead, BlockUpdate, HighlightUpdate, ReorderRequest, SourceCreate, SourceRead, SourceUpdate
from app.schemas.ai_prompt_template import AIPromptTemplateRead, AIPromptTemplateWrite
from app.schemas.auth import UserRead
from app.services.ai_block_analysis import analyze_block
from app.services.ai_enrichment import generate_topic_summary, retry_item_enrichment
from app.services.ai_models import create_ai_model, list_ai_models, serialize_ai_model, set_default_ai_model, update_ai_model
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
            "enable_highlight": source.enable_highlight,
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
    if payload.enable_highlight is not None:
        source.enable_highlight = payload.enable_highlight
    session.commit()
    session.refresh(source)
    return {
        "id": source.id,
        "topic_id": source.topic_id,
        "site": source.site,
        "name": source.name,
        "entry_url": source.entry_url,
        "enabled": source.enabled,
        "enable_highlight": source.enable_highlight,
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


@router.post("/ai/topic-summaries/stocks/regenerate")
def regenerate_stocks_ai_summary(session: Session = Depends(get_session)) -> dict:
    summary = generate_topic_summary(session, topic_slug="stocks", trigger_type="manual")
    session.commit()
    return {"id": summary.id, "version": summary.version, "status": summary.status}


@router.get("/ai-jobs")
def list_ai_jobs(
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    trigger_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    session: Session = Depends(get_session),
) -> AIJobListResponse:
    from datetime import datetime
    stmt = select(AIGenerationJob)
    if status:
        stmt = stmt.where(AIGenerationJob.status == status)
    if trigger_type:
        stmt = stmt.where(AIGenerationJob.trigger_type == trigger_type)
    if date_from:
        try:
            df = datetime.strptime(date_from, "%Y-%m-%d")
            stmt = stmt.where(AIGenerationJob.created_at >= df)
        except ValueError:
            pass
    if date_to:
        try:
            dt = datetime.strptime(date_to + " 23:59:59", "%Y-%m-%d %H:%M:%S")
            stmt = stmt.where(AIGenerationJob.created_at <= dt)
        except ValueError:
            pass

    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    jobs = session.scalars(
        stmt.order_by(AIGenerationJob.created_at.desc())
        .limit(page_size).offset((page - 1) * page_size)
    ).all()
    return AIJobListResponse(
        total=total or 0,
        page=page,
        page_size=page_size,
        items=[
            AIJobRead(
                id=job.id,
                job_type=job.job_type,
                trigger_type=job.trigger_type,
                topic_id=job.topic_id,
                status=job.status,
                input_count=job.input_count,
                success_count=job.success_count,
                failed_count=job.failed_count,
                error_message=job.error_message,
                log_excerpt=job.log_excerpt,
                started_at=job.started_at,
                finished_at=job.finished_at,
                created_at=job.created_at,
            )
            for job in jobs
        ],
    )


@router.get("/ai-jobs/stats")
def get_ai_jobs_stats(session: Session = Depends(get_session)) -> dict:
    from datetime import date, datetime
    today = datetime.combine(date.today(), datetime.min.time())

    def _count(*where_clauses) -> int:
        stmt = select(func.count()).select_from(AIGenerationJob)
        for clause in where_clauses:
            stmt = stmt.where(clause)
        return session.scalar(stmt) or 0

    by_type_rows = session.execute(
        select(AIGenerationJob.job_type, func.count().label("cnt")).group_by(AIGenerationJob.job_type)
    ).all()
    by_trigger_rows = session.execute(
        select(AIGenerationJob.trigger_type, func.count().label("cnt")).group_by(AIGenerationJob.trigger_type)
    ).all()

    return {
        "today_succeeded": _count(AIGenerationJob.status == "succeeded", AIGenerationJob.created_at >= today),
        "today_failed": _count(AIGenerationJob.status == "failed", AIGenerationJob.created_at >= today),
        "today_processing": _count(AIGenerationJob.status.in_(["pending", "processing"]), AIGenerationJob.created_at >= today),
        "total_succeeded": _count(AIGenerationJob.status == "succeeded"),
        "total_failed": _count(AIGenerationJob.status == "failed"),
        "by_type": [{"job_type": r.job_type, "count": r.cnt} for r in by_type_rows],
        "by_trigger": [{"trigger_type": r.trigger_type, "count": r.cnt} for r in by_trigger_rows],
    }


@router.post("/ai-jobs/{job_id}/retry")
def retry_ai_job(job_id: int, session: Session = Depends(get_session)) -> dict:
    try:
        enrichment = retry_item_enrichment(session, job_id)
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg:
            raise HTTPException(status_code=404, detail=msg) from exc
        if "Retry count exceeded" in msg:
            raise HTTPException(status_code=400, detail=msg) from exc
        raise HTTPException(status_code=500, detail=msg) from exc
    session.commit()
    return {"id": enrichment.id, "status": enrichment.status, "retry_count": enrichment.retry_count}


@router.get("/users")
def list_users(session: Session = Depends(get_session)) -> list[dict]:
    users = session.scalars(select(User).order_by(User.created_at.desc())).all()
    return [
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "status": user.status,
            "last_login_at": user.last_login_at,
            "created_at": user.created_at,
        }
        for user in users
    ]


@router.patch("/users/{user_id}")
def update_user_status(user_id: int, payload: dict, session: Session = Depends(get_session)) -> dict:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    status = payload.get("status")
    if status not in {"active", "disabled"}:
        raise HTTPException(status_code=400, detail="Invalid status")
    user.status = status
    session.commit()
    return {"id": user.id, "status": user.status}


_TOPIC_LABELS: dict[str, str] = {
    "stocks": "股票", "football": "足球", "ai": "AI", "summary": "首页",
}


def _resolve_topic(page_route: str | None) -> str:
    if not page_route:
        return "—"
    for part in page_route.strip("/").split("/"):
        if part in _TOPIC_LABELS:
            return _TOPIC_LABELS[part]
    return page_route


@router.get("/ai/token-usages")
def list_token_usages(page: int = 1, page_size: int = 20, session: Session = Depends(get_session)) -> dict:
    total = session.scalar(select(func.count()).select_from(AITokenUsage)) or 0
    usages = session.scalars(
        select(AITokenUsage).order_by(AITokenUsage.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()

    # Batch-resolve context: block analysis + job
    analysis_ids = [u.related_block_analysis_id for u in usages if u.related_block_analysis_id]
    job_ids = [u.related_job_id for u in usages if u.related_job_id]
    analysis_map = {}
    job_map = {}
    if analysis_ids:
        analyses = session.scalars(select(AIBlockAnalysis).where(AIBlockAnalysis.id.in_(analysis_ids))).all()
        analysis_map = {a.id: a for a in analyses}
    if job_ids:
        jobs = session.scalars(select(AIGenerationJob).where(AIGenerationJob.id.in_(job_ids))).all()
        job_map = {j.id: j for j in jobs}

    def _build_item(u: AITokenUsage) -> dict:
        analysis = analysis_map.get(u.related_block_analysis_id) if u.related_block_analysis_id else None
        job = job_map.get(u.related_job_id) if u.related_job_id else None

        block_title = analysis.block_title if analysis else ""
        topic = _resolve_topic(analysis.page_route if analysis else None)

        return {
            "id": u.id,
            "user_id": u.user_id,
            "model_name": u.model_name,
            "usage_type": u.usage_type,
            "prompt_tokens": u.prompt_tokens,
            "completion_tokens": u.completion_tokens,
            "total_tokens": u.total_tokens,
            "estimated": u.estimated,
            "request_status": u.request_status,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "block_title": block_title,
            "topic": topic,
            "finished_at": job.finished_at.isoformat() if (job and job.finished_at) else None,
            "job_status": job.status if job else None,
            "job_error": job.error_message if job else None,
        }

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_build_item(u) for u in usages],
    }


@router.get("/ai/token-usages/stats")
def get_token_usage_stats(session: Session = Depends(get_session)) -> dict:
    from datetime import date, datetime, timedelta
    from sqlalchemy import func as sa_func, cast, Date

    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    days_ago_14 = today - timedelta(days=13)

    # Today totals
    today_tokens = session.scalar(
        select(sa_func.coalesce(sa_func.sum(AITokenUsage.total_tokens), 0))
        .where(AITokenUsage.created_at >= today_start)
    ) or 0

    today_calls = session.scalar(
        select(sa_func.count()).select_from(AITokenUsage)
        .where(AITokenUsage.created_at >= today_start)
    ) or 0

    # Daily trend (last 14 days)
    daily_rows = session.execute(
        select(
            cast(AITokenUsage.created_at, Date).label("day"),
            sa_func.sum(AITokenUsage.total_tokens).label("total_tokens"),
            sa_func.count().label("calls"),
        )
        .where(AITokenUsage.created_at >= datetime.combine(days_ago_14, datetime.min.time()))
        .group_by("day")
        .order_by("day")
    ).all()

    daily_trend = [
        {"date": str(row.day), "total_tokens": row.total_tokens, "calls": row.calls}
        for row in daily_rows
    ]

    # By model
    model_rows = session.execute(
        select(
            AITokenUsage.model_name,
            sa_func.sum(AITokenUsage.total_tokens).label("total_tokens"),
            sa_func.count().label("calls"),
        )
        .group_by(AITokenUsage.model_name)
        .order_by(sa_func.sum(AITokenUsage.total_tokens).desc())
    ).all()

    by_model = [
        {"model_name": row.model_name, "total_tokens": row.total_tokens, "calls": row.calls}
        for row in model_rows
    ]

    # By topic (via AIBlockAnalysis join)
    topic_rows = session.execute(
        select(
            AIBlockAnalysis.page_route,
            sa_func.sum(AITokenUsage.total_tokens).label("total_tokens"),
            sa_func.count().label("calls"),
        )
        .join(AIBlockAnalysis, AITokenUsage.related_block_analysis_id == AIBlockAnalysis.id)
        .group_by(AIBlockAnalysis.page_route)
        .order_by(sa_func.sum(AITokenUsage.total_tokens).desc())
    ).all()

    by_topic = [
        {"topic_slug": _resolve_topic(row.page_route), "total_tokens": row.total_tokens, "calls": row.calls}
        for row in topic_rows
    ]

    # Active models count
    active_models = session.scalar(
        select(sa_func.count(sa_func.distinct(AITokenUsage.model_name)))
        .where(AITokenUsage.created_at >= today_start)
    ) or 0

    return {
        "today_tokens": today_tokens,
        "today_calls": today_calls,
        "active_models": active_models,
        "daily_trend": daily_trend,
        "by_model": by_model,
        "by_topic": by_topic,
    }


@router.get("/ai/ops-stats")
def get_ai_ops_stats(session: Session = Depends(get_session)) -> dict:
    """Combined stats: token usage + job counts."""
    from datetime import date, datetime, timedelta
    from sqlalchemy import func as sa_func, cast, Date

    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    days_ago_14 = today - timedelta(days=13)

    # Token stats
    today_tokens = session.scalar(select(sa_func.coalesce(sa_func.sum(AITokenUsage.total_tokens), 0)).where(AITokenUsage.created_at >= today_start)) or 0
    today_calls = session.scalar(select(sa_func.count()).select_from(AITokenUsage).where(AITokenUsage.created_at >= today_start)) or 0
    active_models = session.scalar(select(sa_func.count(sa_func.distinct(AITokenUsage.model_name))).where(AITokenUsage.created_at >= today_start)) or 0

    # Job stats
    today_succeeded = session.scalar(select(sa_func.count()).select_from(AIGenerationJob).where(AIGenerationJob.status == "succeeded", AIGenerationJob.created_at >= today_start)) or 0
    today_failed = session.scalar(select(sa_func.count()).select_from(AIGenerationJob).where(AIGenerationJob.status == "failed", AIGenerationJob.created_at >= today_start)) or 0

    # Daily trend
    daily_rows = session.execute(
        select(cast(AITokenUsage.created_at, Date).label("day"), sa_func.sum(AITokenUsage.total_tokens).label("tokens"), sa_func.count().label("calls"))
        .where(AITokenUsage.created_at >= datetime.combine(days_ago_14, datetime.min.time()))
        .group_by("day").order_by("day")
    ).all()

    # By model
    model_rows = session.execute(
        select(AITokenUsage.model_name, sa_func.sum(AITokenUsage.total_tokens).label("tokens"), sa_func.count().label("calls"))
        .group_by(AITokenUsage.model_name).order_by(sa_func.sum(AITokenUsage.total_tokens).desc())
    ).all()

    # Job status pie
    job_status_rows = session.execute(
        select(AIGenerationJob.status, sa_func.count().label("cnt")).where(AIGenerationJob.created_at >= today_start).group_by(AIGenerationJob.status)
    ).all()

    return {
        "today_tokens": today_tokens,
        "today_calls": today_calls,
        "active_models": active_models,
        "today_succeeded": today_succeeded,
        "today_failed": today_failed,
        "daily_trend": [{"date": str(r.day), "total_tokens": r.tokens, "calls": r.calls} for r in daily_rows],
        "by_model": [{"model_name": r.model_name, "total_tokens": r.tokens, "calls": r.calls} for r in model_rows],
        "job_status": [{"status": r.status, "count": r.cnt} for r in job_status_rows],
    }


@router.get("/ai/token-usages/{usage_id}")
def get_token_usage_detail(usage_id: int, session: Session = Depends(get_session)) -> dict:
    usage = session.get(AITokenUsage, usage_id)
    if usage is None:
        raise HTTPException(status_code=404, detail="Token usage not found")

    analysis = session.get(AIBlockAnalysis, usage.related_block_analysis_id) if usage.related_block_analysis_id else None

    return {
        "id": usage.id,
        "user_id": usage.user_id,
        "model_name": usage.model_name,
        "usage_type": usage.usage_type,
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
        "estimated": usage.estimated,
        "request_status": usage.request_status,
        "created_at": usage.created_at.isoformat() if usage.created_at else None,
        "block_title": analysis.block_title if analysis else "",
        "topic": _resolve_topic(analysis.page_route if analysis else None),
        "prompt_text": usage.prompt_text,
        "completion_text": usage.completion_text,
    }


@router.post("/ai/block-analyses/{analysis_id}/regenerate")
def regenerate_block_analysis(analysis_id: int, session: Session = Depends(get_session), admin: User = Depends(get_current_user)) -> dict:
    previous = session.get(AIBlockAnalysis, analysis_id)
    if previous is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    analysis = analyze_block(
        session,
        user=admin,
        page_route=previous.page_route,
        block_id=previous.block_id,
        force=True,
    )
    session.commit()
    return {"id": analysis.id, "status": analysis.status}


def _serialize_prompt_template(template: AIPromptTemplate) -> AIPromptTemplateRead:
    return AIPromptTemplateRead(
        id=template.id,
        topic_slug=template.topic_slug,
        content_class=template.content_class,
        topic_context=template.topic_context,
        extra_forbidden=template.extra_forbidden,
        enabled=template.enabled,
        template_version=template.template_version,
        updated_by_user_id=template.updated_by_user_id,
        notes=template.notes,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


@router.get("/ai-prompt-templates", response_model=list[AIPromptTemplateRead])
def list_prompt_templates(session: Session = Depends(get_session)) -> list[AIPromptTemplateRead]:
    templates = session.scalars(
        select(AIPromptTemplate).order_by(AIPromptTemplate.topic_slug, AIPromptTemplate.content_class)
    ).all()
    return [_serialize_prompt_template(template) for template in templates]


@router.post("/ai-prompt-templates", response_model=AIPromptTemplateRead)
def create_prompt_template(
    payload: AIPromptTemplateWrite,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> AIPromptTemplateRead:
    template = AIPromptTemplate(
        topic_slug=payload.topic_slug.strip(),
        content_class=payload.content_class,
        topic_context=payload.topic_context.strip(),
        extra_forbidden=payload.extra_forbidden.strip(),
        enabled=payload.enabled,
        updated_by_user_id=user.id,
        notes=payload.notes.strip(),
    )
    session.add(template)
    session.commit()
    session.refresh(template)
    return _serialize_prompt_template(template)


@router.put("/ai-prompt-templates/{template_id}", response_model=AIPromptTemplateRead)
def update_prompt_template(
    template_id: int,
    payload: AIPromptTemplateWrite,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> AIPromptTemplateRead:
    template = session.get(AIPromptTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Prompt template not found")
    template.topic_slug = payload.topic_slug.strip()
    template.content_class = payload.content_class
    template.topic_context = payload.topic_context.strip()
    template.extra_forbidden = payload.extra_forbidden.strip()
    template.enabled = payload.enabled
    template.notes = payload.notes.strip()
    template.updated_by_user_id = user.id
    template.template_version += 1
    session.commit()
    session.refresh(template)
    return _serialize_prompt_template(template)


@router.delete("/ai-prompt-templates/{template_id}")
def delete_prompt_template(template_id: int, session: Session = Depends(get_session)) -> dict:
    template = session.get(AIPromptTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Prompt template not found")
    session.delete(template)
    session.commit()
    return {"deleted": True}


@router.get("/ai-models")
def list_admin_ai_models(session: Session = Depends(get_session)) -> list[dict]:
    return [serialize_ai_model(model) for model in list_ai_models(session)]


@router.post("/ai-models")
def create_admin_ai_model(payload: AIModelConfigWrite, session: Session = Depends(get_session)) -> dict:
    model = create_ai_model(session, payload)
    session.commit()
    session.refresh(model)
    return serialize_ai_model(model)


@router.put("/ai-models/{model_id}")
def update_admin_ai_model(model_id: int, payload: AIModelConfigWrite, session: Session = Depends(get_session)) -> dict:
    try:
        model = update_ai_model(session, model_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session.commit()
    session.refresh(model)
    return serialize_ai_model(model)


@router.post("/ai-models/{model_id}/set-default")
def set_admin_ai_model_default(model_id: int, session: Session = Depends(get_session)) -> dict:
    try:
        model = set_default_ai_model(session, model_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session.commit()
    session.refresh(model)
    return serialize_ai_model(model)


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

    # Cascade cleanup: null FK → delete children → delete parents
    old_ids = session.scalars(
        select(PageBlock.id).where(PageBlock.page_route == route, PageBlock.status == "published")
    ).all()
    if old_ids:
        analysis_ids = session.scalars(
            select(AIBlockAnalysis.id).where(AIBlockAnalysis.block_id.in_(old_ids))
        ).all()
        if analysis_ids:
            # 1. Break circular FK: ai_block_analyses.token_usage_id → ai_token_usages
            session.execute(
                update(AIBlockAnalysis).where(AIBlockAnalysis.id.in_(analysis_ids)).values(token_usage_id=None)
            )
            # 2. Delete ai_token_usages (FK → ai_block_analyses)
            session.execute(
                delete(AITokenUsage).where(AITokenUsage.related_block_analysis_id.in_(analysis_ids))
            )
            # 3. Delete ai_generation_jobs (FK → ai_block_analyses)
            session.execute(
                delete(AIGenerationJob).where(AIGenerationJob.block_analysis_id.in_(analysis_ids))
            )
            # 4. Delete ai_block_analyses
            session.execute(
                delete(AIBlockAnalysis).where(AIBlockAnalysis.id.in_(analysis_ids))
            )

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
