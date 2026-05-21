from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import CryptoService
from app.models.entities import CrawlJob, Highlight, Source
from app.services.content import save_raw_items
from app.services.summarizer import HighlightDraft
from app.sources.xueqiu import XueqiuAdapter


def run_crawl_job(session: Session, source_id: int, trigger_type: str) -> CrawlJob:
    running = session.scalar(
        select(CrawlJob).where(CrawlJob.source_id == source_id, CrawlJob.status == "running")
    )
    if running is not None:
        return running

    source = session.get(Source, source_id)
    if source is None:
        raise ValueError("Source not found")

    job = CrawlJob(source_id=source_id, trigger_type=trigger_type, status="running", started_at=datetime.now(timezone.utc))
    session.add(job)
    session.flush()

    try:
        cookie = CryptoService(settings.app_secret_key).decrypt(source.cookie_encrypted)
        adapter = XueqiuAdapter()
        drafts = adapter.fetch(source.entry_url, cookie)
        raw_items = save_raw_items(session, source.id, drafts)
        for raw_item in raw_items:
            summary = HighlightDraft(
                title=raw_item.title or "雪球看点",
                summary=raw_item.body[:200],
                related_symbols=[],
                tags=["雪球"],
                score=int(raw_item.metrics_json.get("fav_count", 0)),
            )
            session.add(
                Highlight(
                    topic_id=source.topic_id,
                    raw_item_id=raw_item.id,
                    title=summary.title,
                    summary=summary.summary,
                    related_symbols_json=summary.related_symbols,
                    tags_json=summary.tags,
                    score=summary.score,
                    generated_by_model="fallback-sync",
                )
            )
        job.status = "success"
        job.items_found = len(drafts)
        job.items_saved = len(raw_items)
        job.finished_at = datetime.now(timezone.utc)
        source.last_crawled_at = job.finished_at
    except Exception as exc:
        job.status = "failed"
        job.error_message = str(exc)
        job.log_excerpt = str(exc)[:500]
        job.finished_at = datetime.now(timezone.utc)
    session.commit()
    return job
