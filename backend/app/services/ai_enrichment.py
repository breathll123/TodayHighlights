from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import AIItemEnrichment, RawItem

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
