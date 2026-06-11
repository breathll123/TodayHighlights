from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from app.core.config import SH_TZ, settings
from app.core.database import SessionLocal
from app.models.entities import Source
from app.services.cleanup import run_full_cleanup
from app.services.jobs import run_crawl_job


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


def create_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    scheduler.add_job(crawl_enabled_sources, "interval", minutes=1, id="crawl_enabled_sources", replace_existing=True)
    scheduler.add_job(scheduled_cleanup, "interval", hours=6, id="scheduled_cleanup", replace_existing=True)

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
