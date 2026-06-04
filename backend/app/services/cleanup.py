"""Data lifecycle cleanup — removes expired / stale data to prevent unbounded growth."""
import logging
from datetime import datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import SH_TZ
from app.models.entities import CrawlJob, Highlight, RawItem

logger = logging.getLogger(__name__)

# Retention thresholds
CRAWL_JOBS_RETENTION_DAYS = 30


def cleanup_expired_raw_items(session: Session) -> int:
    """Delete raw_items that have passed their expires_at and are no longer active.

    Also deletes associated highlights (cascade would be cleaner, but this is explicit).
    """
    now = datetime.now(SH_TZ).replace(tzinfo=None)

    # 1. Find expired item IDs
    expired_ids = session.scalars(
        select_expired_ids(now)
    ).all()

    if not expired_ids:
        return 0

    # 2. Delete associated highlights first (FK constraint)
    deleted_highlights = session.execute(
        delete(Highlight).where(Highlight.raw_item_id.in_(expired_ids))
    ).rowcount

    # 3. Delete the raw items
    deleted_items = session.execute(
        delete(RawItem).where(RawItem.id.in_(expired_ids))
    ).rowcount

    session.commit()
    logger.info(
        "Cleanup: deleted %d expired raw_items and %d associated highlights",
        deleted_items, deleted_highlights,
    )
    return deleted_items


def select_expired_ids(now: datetime):
    """Helper: select IDs of expired, active raw_items."""
    from sqlalchemy import select
    return (
        select(RawItem.id)
        .where(RawItem.status == "active", RawItem.expires_at < now)
        .limit(5000)  # Batch to avoid huge deletes
    )


def cleanup_old_crawl_jobs(session: Session) -> int:
    """Delete crawl_jobs older than retention period."""
    cutoff = datetime.now(SH_TZ).replace(tzinfo=None) - timedelta(days=CRAWL_JOBS_RETENTION_DAYS)

    deleted = session.execute(
        delete(CrawlJob).where(CrawlJob.created_at < cutoff)
    ).rowcount

    if deleted:
        session.commit()
        logger.info("Cleanup: deleted %d old crawl_jobs (before %s)", deleted, cutoff)
    return deleted


def cleanup_orphaned_highlights(session: Session) -> int:
    """Delete highlights whose raw_item no longer exists."""
    from sqlalchemy import select as sa_select

    orphan_ids = session.scalars(
        sa_select(Highlight.id)
        .outerjoin(RawItem, Highlight.raw_item_id == RawItem.id)
        .where(RawItem.id.is_(None))
        .limit(1000)
    ).all()

    if not orphan_ids:
        return 0

    deleted = session.execute(
        delete(Highlight).where(Highlight.id.in_(orphan_ids))
    ).rowcount

    session.commit()
    logger.info("Cleanup: deleted %d orphaned highlights", deleted)
    return deleted


def run_full_cleanup(session: Session) -> dict[str, int]:
    """Run all cleanup tasks. Called by scheduler periodically."""
    return {
        "expired_raw_items": cleanup_expired_raw_items(session),
        "old_crawl_jobs": cleanup_old_crawl_jobs(session),
        "orphaned_highlights": cleanup_orphaned_highlights(session),
    }
