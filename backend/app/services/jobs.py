import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import SH_TZ, settings
from app.core.crypto import CryptoService
from app.models.entities import CrawlJob, Highlight, Source
from app.services.content import save_raw_items
from app.services.settings import get_plain_setting, get_secret_setting
from app.services.summarizer import HighlightDraft, SummarizerClient
from app.sources import get_adapter


def _summarize_sync(base_url: str, api_key: str, model: str, title: str, body: str) -> HighlightDraft:
    return asyncio.run(SummarizerClient(base_url, api_key, model).summarize(title, body))


def _generate_highlights(session: Session, source: Source, raw_items: list) -> None:
    model_name = get_plain_setting(session, "llm.model")
    base_url = get_plain_setting(session, "llm.base_url")
    api_key = get_secret_setting(session, "llm.api_key")
    use_ai = bool(model_name and base_url and api_key)

    for raw_item in raw_items:
        if use_ai:
            try:
                summary = _summarize_sync(base_url, api_key, model_name, raw_item.title, raw_item.body)
                generated_by = model_name
            except Exception:
                summary = HighlightDraft(
                    title=raw_item.title or "看点",
                    summary=raw_item.body[:200],
                    related_symbols=[],
                    tags=[],
                    score=int(raw_item.metrics_json.get("like_count", 0)) + int(raw_item.metrics_json.get("view_count", 0) // 1000),
                )
                generated_by = "fallback-ai-failed"
        else:
            summary = HighlightDraft(
                title=raw_item.title or "看点",
                summary=raw_item.body[:200],
                related_symbols=[],
                tags=[],
                score=int(raw_item.metrics_json.get("like_count", 0)) + int(raw_item.metrics_json.get("view_count", 0) // 1000),
            )
            generated_by = "fallback-sync"

        session.add(
            Highlight(
                topic_id=source.topic_id,
                raw_item_id=raw_item.id,
                title=summary.title,
                summary=summary.summary,
                related_symbols_json=summary.related_symbols,
                tags_json=summary.tags,
                score=summary.score,
                generated_by_model=generated_by,
            )
        )


def run_crawl_job(session: Session, source_id: int, trigger_type: str) -> CrawlJob:
    running = session.scalar(
        select(CrawlJob).where(CrawlJob.source_id == source_id, CrawlJob.status == "running")
    )
    if running is not None:
        return running

    source = session.get(Source, source_id)
    if source is None:
        raise ValueError("Source not found")

    job = CrawlJob(source_id=source_id, trigger_type=trigger_type, status="running", started_at=datetime.now(SH_TZ))
    session.add(job)
    session.flush()

    try:
        cookie = CryptoService(settings.app_secret_key).decrypt(source.cookie_encrypted)
        adapter = get_adapter(source.site)
        drafts = adapter.fetch(source.entry_url, cookie)
        raw_items = save_raw_items(session, source.id, drafts)

        if source.enable_highlight:
            _generate_highlights(session, source, raw_items)

        job.status = "success"
        job.items_found = len(drafts)
        job.items_saved = len(raw_items)
        job.finished_at = datetime.now(SH_TZ)
        source.last_crawled_at = job.finished_at
        source.next_crawl_at = (job.finished_at or datetime.now(SH_TZ)).replace(tzinfo=None) + timedelta(minutes=source.crawl_interval_minutes)
    except Exception as exc:
        job.status = "failed"
        job.error_message = str(exc)
        job.log_excerpt = str(exc)[:500]
        job.finished_at = datetime.now(SH_TZ)
        source.last_crawled_at = job.finished_at
        source.next_crawl_at = job.finished_at.replace(tzinfo=None) + timedelta(minutes=source.crawl_interval_minutes)
    session.commit()
    return job
