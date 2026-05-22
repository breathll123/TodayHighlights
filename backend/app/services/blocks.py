from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Highlight, PageBlock


def resolve_block_data(session: Session, block: PageBlock) -> list[dict]:
    source_type = block.source_type
    config = block.source_config or {}
    limit = block.display_count

    if source_type == "topic":
        topic_id = config.get("topic_id", 1)
        stmt = (
            select(Highlight)
            .where(Highlight.topic_id == topic_id, Highlight.is_hidden.is_(False))
            .order_by(Highlight.is_pinned.desc(), Highlight.score.desc(), Highlight.created_at.desc())
            .limit(limit)
        )
        highlights = session.scalars(stmt).all()
        return [
            {
                "id": h.id,
                "title": h.title,
                "summary": h.summary,
                "related_symbols_json": h.related_symbols_json,
                "tags_json": h.tags_json,
                "score": h.score,
                "is_pinned": h.is_pinned,
                "created_at": h.created_at.isoformat() if h.created_at else None,
            }
            for h in highlights
        ]

    # hot_stocks / hot_events / search / screener deferred
    return []


def get_page_blocks(session: Session, route: str) -> list[dict]:
    stmt = (
        select(PageBlock)
        .where(PageBlock.page_route == route, PageBlock.enabled.is_(True))
        .order_by(PageBlock.sort_order)
    )
    blocks = session.scalars(stmt).all()
    result = []
    for block in blocks:
        item = {
            "id": block.id,
            "title": block.title,
            "sort_order": block.sort_order,
            "display_style": block.display_style,
            "display_count": block.display_count,
            "source_type": block.source_type,
            "data": resolve_block_data(session, block),
        }
        result.append(item)
    return result
