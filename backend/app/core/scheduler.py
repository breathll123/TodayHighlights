from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.entities import Source
from app.services.jobs import run_crawl_job


def crawl_enabled_sources() -> None:
    with SessionLocal() as session:
        sources = session.scalars(select(Source).where(Source.enabled.is_(True))).all()
        for source in sources:
            run_crawl_job(session, source.id, "scheduled")


def create_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    scheduler.add_job(crawl_enabled_sources, "interval", minutes=5, id="crawl_enabled_sources", replace_existing=True)
    return scheduler
