import logging
from datetime import datetime

from apscheduler.events import (EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, EVENT_JOB_MAX_INSTANCES,
                                 EVENT_JOB_MISSED, EVENT_SCHEDULER_START, EVENT_SCHEDULER_SHUTDOWN)
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from app.core.config import SH_TZ, settings
from app.core.database import SessionLocal
from app.core.logging import log_event
from app.models.entities import Source
from app.services.cleanup import run_full_cleanup
from app.services.jobs import run_crawl_job

logger = logging.getLogger("today_highlights.scheduler")

SCHEDULER_JOB_NAMES = {
    "crawl_enabled_sources": "采集已启用数据源",
    "scheduled_cleanup": "清理过期数据",
    "artificial_analysis_morning": "同步模型榜单（早间）",
    "artificial_analysis_evening": "同步模型榜单（晚间）",
}


def _scheduler_job_name(job_id: str) -> str:
    return SCHEDULER_JOB_NAMES.get(job_id, job_id)


def crawl_enabled_sources() -> None:
    with SessionLocal() as session:
        now = datetime.now(SH_TZ)
        sources = session.scalars(
            select(Source).where(
                Source.enabled.is_(True),
                (Source.next_crawl_at.is_(None)) | (Source.next_crawl_at <= now),
            )
        ).all()
        for source in sources:
            run_crawl_job(session, source.id, "scheduled")


def scheduled_cleanup() -> None:
    with SessionLocal() as session:
        run_full_cleanup(session)


def _handle_scheduler_event(event) -> None:
    job_id = str(event.job_id)
    job_name = _scheduler_job_name(job_id)
    if event.code == EVENT_JOB_EXECUTED:
        log_event(
            logger,
            channel="application",
            category="scheduler",
            event="scheduler.job.completed",
            job_id=job_id,
            job_name=job_name,
        )
    elif event.code == EVENT_JOB_ERROR:
        log_event(
            logger,
            channel="application",
            category="scheduler",
            event="scheduler.job.failed",
            level=logging.ERROR,
            job_id=job_id,
            job_name=job_name,
            error_type=type(event.exception).__name__ if event.exception else "-",
            error=str(event.exception or ""),
        )
    elif event.code == EVENT_JOB_MISSED:
        log_event(
            logger,
            channel="application",
            category="scheduler",
            event="scheduler.job.missed",
            level=logging.WARNING,
            job_id=job_id,
            job_name=job_name,
        )
    elif event.code == EVENT_JOB_MAX_INSTANCES:
        log_event(
            logger,
            channel="application",
            category="scheduler",
            event="scheduler.job.skipped",
            level=logging.WARNING,
            job_id=job_id,
            job_name=job_name,
            reason="max_instances",
        )


def create_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    scheduler.add_listener(_handle_scheduler_event, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR | EVENT_JOB_MISSED | EVENT_JOB_MAX_INSTANCES)
    scheduler.add_job(crawl_enabled_sources, "interval", minutes=1, id="crawl_enabled_sources", replace_existing=True)
    scheduler.add_job(scheduled_cleanup, "interval", hours=6, id="scheduled_cleanup", replace_existing=True)

    log_event(logger, channel="application", category="scheduler", event="scheduler_started",
              job_ids=[job.id for job in scheduler.get_jobs()])

    if settings.artificial_analysis_sync_enabled and settings.artificial_analysis_api_key:
        from app.services.artificial_analysis.sync import scheduled_sync

        def _parse_hh_mm(value: str) -> tuple[int, int]:
            parts = value.strip().split(":")
            return int(parts[0]), int(parts[1])

        morning_h, morning_m = _parse_hh_mm(settings.artificial_analysis_schedule_morning)
        evening_h, evening_m = _parse_hh_mm(settings.artificial_analysis_schedule_evening)

        scheduler.add_job(
            scheduled_sync, "cron", hour=morning_h, minute=morning_m,
            id="artificial_analysis_morning", replace_existing=True,
        )
        scheduler.add_job(
            scheduled_sync, "cron", hour=evening_h, minute=evening_m,
            id="artificial_analysis_evening", replace_existing=True,
        )

    return scheduler
