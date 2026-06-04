from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Highlight, RawItem, Source
from app.sources.base import RawItemDraft


def _calc_expires_at(source: Source) -> datetime:
    """Calculate expiration time based on source crawl interval.

    Short-interval sources (≤10 min) keep data for 3 days.
    Normal sources keep data for 7 days.
    """
    if source.crawl_interval_minutes <= 10:
        return datetime.utcnow() + timedelta(days=3)
    return datetime.utcnow() + timedelta(days=7)


def save_raw_items(session: Session, source_id: int, drafts: list[RawItemDraft]) -> list[RawItem]:
    source = session.get(Source, source_id)
    expires_at = _calc_expires_at(source) if source else datetime.utcnow() + timedelta(days=7)

    saved: list[RawItem] = []
    for draft in drafts:
        existing = session.scalar(
            select(RawItem).where(
                RawItem.source_id == source_id,
                RawItem.external_id == draft.external_id,
            )
        )
        if existing is not None:
            if existing.content_hash == draft.content_hash:
                continue
            existing.url = draft.url
            existing.title = draft.title
            existing.body = draft.body
            existing.metrics_json = draft.metrics
            existing.content_hash = draft.content_hash
            existing.published_at = draft.published_at
            existing.author = draft.author
            if draft.raw_snapshot:
                existing.raw_snapshot = draft.raw_snapshot
            existing.expires_at = expires_at
            existing.status = "active"
            saved.append(existing)
            continue

        item = RawItem(
            source_id=source_id,
            external_id=draft.external_id,
            url=draft.url,
            author=draft.author,
            title=draft.title,
            body=draft.body,
            published_at=draft.published_at,
            metrics_json=draft.metrics,
            content_hash=draft.content_hash,
            raw_snapshot=draft.raw_snapshot or None,
            status="active",
            expires_at=expires_at,
        )
        session.add(item)
        saved.append(item)
        session.flush()
    return saved


def update_highlight_review(
    session: Session,
    highlight_id: int,
    *,
    title: str,
    summary: str,
    is_pinned: bool,
    is_hidden: bool,
) -> Highlight:
    highlight = session.get(Highlight, highlight_id)
    if highlight is None:
        raise ValueError("Highlight not found")
    highlight.title = title
    highlight.summary = summary
    highlight.is_pinned = is_pinned
    highlight.is_hidden = is_hidden
    highlight.review_status = "reviewed"
    session.flush()
    return highlight
