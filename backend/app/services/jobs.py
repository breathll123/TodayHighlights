import asyncio
import logging
import time
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import SH_TZ, settings
from app.core.crypto import CryptoService
from app.core.logging import bind_log_context, format_duration, log_event
from app.models.entities import CrawlJob, Highlight, Source
from app.services.ai_enrichment import create_pending_enrichments, process_item_enrichment, select_item_candidates

logger = logging.getLogger("today_highlights.crawler")
from app.services.content import save_raw_items
from app.services.settings import get_plain_setting, get_secret_setting
from app.services.skills.providers import SITE_TO_SOURCE
from app.services.skills.sync import run_provider_sync_inline
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
    session.commit()  # 立即提交抓取任务记录，让前端“任务”页面的进度轮询能立刻看到 running 状态的实例

    topic_name = source.topic.name if source.topic else "-"
    with bind_log_context(
        crawl_job_id=job.id,
        job_id=job.id,
        source_id=source.id,
        source_name=source.name,
        topic_name=topic_name,
    ):
        log_event(
            logger,
            channel="application",
            category="crawler",
            event="crawl.started",
            site=source.site,
            trigger=trigger_type,
        )
        started = time.perf_counter()
        stage = "fetch"

        try:
            # Skills sources (e.g. github_skills) don't crawl into RawItems — they
            # run the skills pipeline (fetch → classify → translate) and report
            # candidate/kept counts as the job's found/saved.
            if source.site in SITE_TO_SOURCE:
                stage = "skills_sync"
                summary = run_provider_sync_inline(session, source)
                job.status = "success"
                job.items_found = summary.get("candidates", 0)
                job.items_saved = summary.get("kept", 0)
                job.finished_at = datetime.now(SH_TZ)
                source.last_crawled_at = job.finished_at
                source.next_crawl_at = job.finished_at.replace(tzinfo=None) + timedelta(minutes=source.crawl_interval_minutes)
                log_event(
                    logger, channel="application", category="crawler", event="crawl.completed",
                    status="success", found=job.items_found, saved=job.items_saved,
                    duration=format_duration(time.perf_counter() - started),
                )
                session.commit()
                return job

            stage = "decrypt"
            cookie = CryptoService(settings.app_secret_key).decrypt(source.cookie_encrypted)

            stage = "fetch"
            adapter = get_adapter(source.site)
            drafts = adapter.fetch(source.entry_url, cookie)
            log_event(
                logger,
                channel="application",
                category="crawler",
                event="crawl.fetch.completed",
                stage=stage,
                found=len(drafts),
                duration=format_duration(time.perf_counter() - started),
            )

            stage = "persist"
            raw_items = save_raw_items(session, source.id, drafts)
            items_received = len(drafts)
            items_saved = len(raw_items)
            items_deduplicated = max(0, items_received - items_saved)
            log_event(
                logger,
                channel="application",
                category="crawler",
                event="crawl.persist.completed",
                stage=stage,
                received=items_received,
                saved=items_saved,
                deduplicated=items_deduplicated,
            )

            if source.enable_highlight:
                stage = "enrichment"
                candidates = select_item_candidates(session, source.topic_id, raw_items, limit=50)
                if candidates:
                    enrichments = create_pending_enrichments(session, source.topic_id, candidates)
                    for enrichment in enrichments:
                        try:
                            process_item_enrichment(session, enrichment.id, trigger_type=trigger_type)
                        except Exception as exc:
                            log_event(
                                logger, channel="application", category="crawler",
                                event="crawl.enrichment.failed", level=logging.WARNING,
                                stage="enrichment", enrichment_id=enrichment.id,
                                error_type=type(exc).__name__, error=str(exc),
                            )

            job.status = "success"
            job.items_found = len(drafts)
            job.items_saved = len(raw_items)
            job.finished_at = datetime.now(SH_TZ)
            source.last_crawled_at = job.finished_at
            source.next_crawl_at = (job.finished_at or datetime.now(SH_TZ)).replace(tzinfo=None) + timedelta(minutes=source.crawl_interval_minutes)

            log_event(
                logger,
                channel="application",
                category="crawler",
                event="crawl.completed",
                status="success",
                found=job.items_found,
                saved=job.items_saved,
                duration=format_duration(time.perf_counter() - started),
            )

        except Exception as exc:
            job.status = "failed"
            job.error_message = str(exc)
            job.log_excerpt = str(exc)[:500]
            job.finished_at = datetime.now(SH_TZ)
            source.last_crawled_at = job.finished_at
            source.next_crawl_at = job.finished_at.replace(tzinfo=None) + timedelta(minutes=source.crawl_interval_minutes)

            log_event(
                logger,
                channel="application",
                category="crawler",
                event="crawl.failed",
                level=logging.ERROR,
                stage=stage,
                error_type=type(exc).__name__,
                error=str(exc),
                duration=format_duration(time.perf_counter() - started),
            )
    session.commit()
    return job


def stop_job(session: Session, job_id: int) -> CrawlJob:
    """Stop a stuck/running job, releasing the per-source running guard so new
    crawls can start.

    This does NOT kill an in-flight worker thread (Python threads aren't
    forcibly killable, and a zombie left by a process restart has no thread at
    all) — it releases the DB lock. If a thread really is still alive it will
    overwrite the status when it finishes; for the common case (a zombie that
    never finishes) the 'stopped' state sticks. Idempotent: a job that already
    finished is returned untouched.
    """
    job = session.get(CrawlJob, job_id)
    if job is None:
        raise ValueError("Job not found")
    if job.status == "running":
        job.status = "stopped"
        job.error_message = job.error_message or "手动停止"
        job.finished_at = datetime.now(SH_TZ)
        session.commit()
        log_event(
            logger, channel="application", category="crawler", event="crawl.stopped",
            crawl_job_id=job.id, job_id=job.id, source_id=job.source_id,
        )
    return job


def reconcile_stale_jobs(session: Session) -> int:
    """On startup: any job still 'running' was orphaned by a process restart —
    its worker thread is gone and can never resume. Mark them failed so a
    restart never permanently blocks a source via the running guard. Returns
    how many were reconciled.
    """
    stale = session.scalars(select(CrawlJob).where(CrawlJob.status == "running")).all()
    for job in stale:
        job.status = "failed"
        job.error_message = job.error_message or "进程重启，任务中断未完成"
        job.finished_at = datetime.now(SH_TZ)
    if stale:
        session.commit()
        log_event(
            logger, channel="application", category="crawler",
            event="crawl.reconciled", count=len(stale),
        )
    return len(stale)
