from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import CryptoService
from app.models.entities import AIGenerationJob, AIItemEnrichment, AIModelConfig, AITopicSummary, Highlight, RawItem, Topic
from app.services.ai_client import AIClient, PostJson
from app.services.ai_models import get_default_ai_model
from app.services.ai_prompts import ITEM_SYSTEM_PROMPT, TOPIC_SYSTEM_PROMPT, item_user_prompt, topic_user_prompt
from app.services.ai_validation import validate_item_enrichment_payload, validate_topic_summary_payload

ITEM_WINDOW_HOURS = 24
MIN_TITLE_CHARS = 6
MIN_CONTENT_CHARS = 40
CRAWL_ITEM_LIMIT = 50
BACKFILL_ITEM_LIMIT = 200


def _normalized_title(title: str) -> str:
    return "".join(title.split()).lower()


def _published_or_created(raw_item: RawItem) -> datetime:
    return raw_item.published_at or raw_item.created_at


def select_item_candidates(session: Session, topic_id: int, raw_items: list[RawItem], *, limit: int) -> list[RawItem]:
    cutoff = datetime.utcnow() - timedelta(hours=ITEM_WINDOW_HOURS)
    raw_ids = [item.id for item in raw_items if item.id is not None]
    existing_ids = set(
        session.scalars(select(AIItemEnrichment.raw_item_id).where(AIItemEnrichment.raw_item_id.in_(raw_ids))).all()
    )
    seen_titles: set[str] = set()
    candidates: list[RawItem] = []
    for item in sorted(raw_items, key=_published_or_created, reverse=True):
        if item.id in existing_ids:
            continue
        if _published_or_created(item) < cutoff:
            continue
        title = item.title.strip()
        body = item.body.strip()
        if len(title) < MIN_TITLE_CHARS:
            continue
        if len(" ".join((title, body)).strip()) < MIN_CONTENT_CHARS:
            continue
        title_key = _normalized_title(title)
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)
        candidates.append(item)
        if len(candidates) >= limit:
            break
    return candidates


def create_pending_enrichments(session: Session, topic_id: int, raw_items: list[RawItem]) -> list[AIItemEnrichment]:
    """Create pending AIItemEnrichment records for each candidate raw item."""
    enrichments: list[AIItemEnrichment] = []
    for item in raw_items:
        enrichment = AIItemEnrichment(
            topic_id=topic_id,
            raw_item_id=item.id,
            status="pending",
        )
        session.add(enrichment)
        enrichments.append(enrichment)
    session.flush()
    return enrichments


def _build_job(
    job_type: str,
    trigger_type: str,
    status: str,
    topic_id: int | None = None,
    raw_item_id: int | None = None,
    item_enrichment_id: int | None = None,
    topic_summary_id: int | None = None,
    model_config_id: int | None = None,
    input_count: int = 0,
    success_count: int = 0,
    failed_count: int = 0,
    retry_of_job_id: int | None = None,
    error_message: str = "",
    log_excerpt: str = "",
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> AIGenerationJob:
    return AIGenerationJob(
        job_type=job_type,
        trigger_type=trigger_type,
        topic_id=topic_id,
        raw_item_id=raw_item_id,
        item_enrichment_id=item_enrichment_id,
        topic_summary_id=topic_summary_id,
        model_config_id=model_config_id,
        status=status,
        input_count=input_count,
        success_count=success_count,
        failed_count=failed_count,
        retry_of_job_id=retry_of_job_id,
        error_message=error_message,
        log_excerpt=log_excerpt,
        started_at=started_at,
        finished_at=finished_at,
    )


def sync_highlight_from_enrichment(session: Session, enrichment: AIItemEnrichment) -> Highlight:
    """Create or update a Highlight row from a generated enrichment."""
    existing = session.scalar(
        select(Highlight).where(Highlight.raw_item_id == enrichment.raw_item_id)
    )
    if existing is not None:
        existing.title = enrichment.generated_title
        existing.summary = enrichment.summary
        existing.tags_json = enrichment.tags_json
        existing.related_symbols_json = enrichment.related_symbols_json
        existing.score = enrichment.importance_score
        existing.generated_by_model = enrichment.generated_by_model
        session.flush()
        return existing

    highlight = Highlight(
        topic_id=enrichment.topic_id,
        raw_item_id=enrichment.raw_item_id,
        title=enrichment.generated_title,
        summary=enrichment.summary,
        related_symbols_json=enrichment.related_symbols_json,
        tags_json=enrichment.tags_json,
        score=enrichment.importance_score,
        generated_by_model=enrichment.generated_by_model,
    )
    session.add(highlight)
    session.flush()
    return highlight


def process_item_enrichment(
    session: Session,
    enrichment_id: int,
    post_json: PostJson | None = None,
    trigger_type: str = "crawl",
    retry_of_job_id: int | None = None,
) -> AIItemEnrichment:
    """Process a single pending enrichment: call AI, validate, sync to highlight, log job."""
    enrichment = session.get(AIItemEnrichment, enrichment_id)
    if enrichment is None:
        raise ValueError("Enrichment not found")

    # Set processing state
    enrichment.status = "processing"
    if trigger_type == "retry":
        enrichment.retry_count += 1
    enrichment.last_attempted_at = datetime.utcnow()
    session.flush()

    # Reject if retry limit exceeded
    if enrichment.retry_count > 3:
        enrichment.status = "failed"
        enrichment.error_message = "Retry count exceeded"
        session.flush()
        return enrichment

    # Get default model
    model_cfg = get_default_ai_model(session)
    if model_cfg is None:
        raise ValueError("No default AI model configured")

    # Get raw item for content
    raw_item = enrichment.raw_item_id

    started_at = datetime.utcnow()

    try:
        # Decrypt API key and build client
        crypto = CryptoService(settings.app_secret_key)
        api_key = crypto.decrypt(model_cfg.api_key_encrypted)
        client = AIClient(
            base_url=model_cfg.base_url,
            api_key=api_key,
            model=model_cfg.model,
            post_json=post_json,
        )

        # Call AI - need to run async in sync context
        import asyncio

        raw = session.get(RawItem, raw_item)
        if raw is None:
            raise ValueError("Raw item not found")

        result = asyncio.run(
            client.complete_json(
                ITEM_SYSTEM_PROMPT,
                item_user_prompt(
                    title=raw.title,
                    source_name=raw.author or "未知来源",
                    published_at=raw.published_at.isoformat() if raw.published_at else "",
                    body=raw.body,
                ),
            )
        )

        # Validate
        validated = validate_item_enrichment_payload(result)

        # Save generated fields
        enrichment.generated_title = validated.title
        enrichment.summary = validated.summary
        enrichment.tags_json = validated.tags
        enrichment.related_symbols_json = validated.related_symbols
        enrichment.importance_score = validated.importance_score
        enrichment.focus_points_json = validated.focus_points
        enrichment.risk_points_json = validated.risk_points
        enrichment.model_config_id = model_cfg.id
        enrichment.generated_by_model = model_cfg.model
        enrichment.generated_at = datetime.utcnow()
        enrichment.status = "generated"
        session.flush()

        # Sync to highlight
        sync_highlight_from_enrichment(session, enrichment)

        # Log success job
        job = _build_job(
            job_type="item_enrichment",
            trigger_type=trigger_type,
            status="succeeded",
            topic_id=enrichment.topic_id,
            raw_item_id=enrichment.raw_item_id,
            item_enrichment_id=enrichment.id,
            model_config_id=model_cfg.id,
            input_count=1,
            success_count=1,
            retry_of_job_id=retry_of_job_id,
            started_at=started_at,
            finished_at=datetime.utcnow(),
        )
        session.add(job)

    except Exception as exc:
        enrichment.status = "failed"
        enrichment.error_message = str(exc)[:500]
        session.flush()

        # Log failure job
        job = _build_job(
            job_type="item_enrichment",
            trigger_type=trigger_type,
            status="failed",
            topic_id=enrichment.topic_id,
            raw_item_id=enrichment.raw_item_id,
            item_enrichment_id=enrichment.id,
            model_config_id=model_cfg.id if model_cfg else None,
            retry_of_job_id=retry_of_job_id,
            error_message=str(exc)[:500],
            started_at=started_at,
            finished_at=datetime.utcnow(),
        )
        session.add(job)

    return enrichment


def retry_item_enrichment(session: Session, job_id: int, post_json: PostJson | None = None) -> AIItemEnrichment:
    """Retry a failed enrichment from its job record."""
    job = session.get(AIGenerationJob, job_id)
    if job is None:
        raise ValueError("Job not found")
    if job.item_enrichment_id is None:
        raise ValueError("Job has no associated enrichment")
    enrichment = session.get(AIItemEnrichment, job.item_enrichment_id)
    if enrichment is None:
        raise ValueError("Enrichment not found")
    if enrichment.retry_count >= 3:
        raise ValueError("Retry count exceeded")
    return process_item_enrichment(
        session,
        enrichment.id,
        post_json=post_json,
        trigger_type="retry",
        retry_of_job_id=job_id,
    )


def generate_topic_summary(
    session: Session,
    topic_slug: str,
    trigger_type: str = "manual",
    post_json: PostJson | None = None,
) -> AITopicSummary:
    """Generate an AI topic summary from recent enrichments and signals."""
    import asyncio
    import json as _json

    topic = session.scalar(select(Topic).where(Topic.slug == topic_slug, Topic.enabled.is_(True)))
    if topic is None:
        raise ValueError("Topic not found")

    model_cfg = get_default_ai_model(session)
    if model_cfg is None:
        raise ValueError("No default AI model configured")

    # Gather recent generated enrichments (last 24 hours)
    cutoff = datetime.utcnow() - timedelta(hours=24)
    enrichments = session.scalars(
        select(AIItemEnrichment)
        .where(
            AIItemEnrichment.topic_id == topic.id,
            AIItemEnrichment.status == "generated",
            AIItemEnrichment.generated_at >= cutoff,
        )
        .order_by(AIItemEnrichment.importance_score.desc())
        .limit(20)
    ).all()

    # Build context for the AI
    enrichment_data = [
        {
            "id": e.id,
            "title": e.generated_title,
            "summary": e.summary,
            "tags": e.tags_json,
            "importance_score": e.importance_score,
            "focus_points": e.focus_points_json,
            "risk_points": e.risk_points_json,
        }
        for e in enrichments
    ]

    context = _json.dumps({"enrichments": enrichment_data}, ensure_ascii=False)

    # Determine next version for today
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    latest = session.scalar(
        select(AITopicSummary)
        .where(AITopicSummary.topic_id == topic.id, AITopicSummary.summary_date == today)
        .order_by(AITopicSummary.version.desc())
        .limit(1)
    )
    next_version = (latest.version + 1) if latest else 1

    started_at = datetime.utcnow()

    try:
        crypto = CryptoService(settings.app_secret_key)
        api_key = crypto.decrypt(model_cfg.api_key_encrypted)
        client = AIClient(
            base_url=model_cfg.base_url,
            api_key=api_key,
            model=model_cfg.model,
            post_json=post_json,
        )

        result = asyncio.run(
            client.complete_json(TOPIC_SYSTEM_PROMPT, topic_user_prompt(context))
        )

        validated = validate_topic_summary_payload(result)

        summary = AITopicSummary(
            topic_id=topic.id,
            summary_date=today,
            version=next_version,
            status="generated",
            title=validated.title,
            items_json=[
                {
                    "title": item.title,
                    "reason": item.reason,
                    "related": item.related,
                    "risk": item.risk,
                    "source_refs": item.source_refs,
                }
                for item in validated.items
            ],
            source_refs_json=[],
            model_config_id=model_cfg.id,
            generated_by_model=model_cfg.model,
            generated_at=datetime.utcnow(),
        )
        session.add(summary)
        session.flush()

        job = _build_job(
            job_type="topic_summary",
            trigger_type=trigger_type,
            status="succeeded",
            topic_id=topic.id,
            topic_summary_id=summary.id,
            model_config_id=model_cfg.id,
            input_count=len(enrichments),
            success_count=1,
            started_at=started_at,
            finished_at=datetime.utcnow(),
        )
        session.add(job)

        return summary

    except Exception as exc:
        job = _build_job(
            job_type="topic_summary",
            trigger_type=trigger_type,
            status="failed",
            topic_id=topic.id,
            model_config_id=model_cfg.id,
            error_message=str(exc)[:500],
            started_at=started_at,
            finished_at=datetime.utcnow(),
        )
        session.add(job)
        raise
