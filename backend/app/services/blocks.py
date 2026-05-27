from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.entities import Highlight, PageBlock, RawItem, Source
from app.services.adapters.xueqiu import get_cookie, fetch_hot_events, fetch_hot_stocks, fetch_screener
from app.services.adapters.eastmoney import (
    fetch_announcements, fetch_capital_flow, fetch_gainers,
    fetch_indices, fetch_industry, fetch_losers, fetch_sectors,
)
def resolve_block_data(session: Session, block: PageBlock) -> list[dict]:
    source_type = block.source_type
    config = block.source_config or {}
    limit = block.display_count

    if source_type == "topic":
        topic_id = config.get("topic_id", 1)
        stmt = (
            select(Highlight)
            .options(joinedload(Highlight.raw_item))
            .where(Highlight.topic_id == topic_id, Highlight.is_hidden.is_(False))
            .order_by(Highlight.is_pinned.desc(), Highlight.score.desc(), Highlight.created_at.desc())
            .limit(limit)
        )
        highlights = session.scalars(stmt).unique().all()
        return [
            {
                "id": h.id,
                "title": h.title,
                "summary": h.summary,
                "url": h.raw_item.url if h.raw_item else None,
                "related_symbols_json": h.related_symbols_json,
                "tags_json": h.tags_json,
                "score": h.score,
                "is_pinned": h.is_pinned,
                "created_at": h.created_at.isoformat() if h.created_at else None,
            }
            for h in highlights
        ]

    if source_type == "raw":
        source_id = config.get("source_id")
        if source_id is None:
            return []
        stmt = (
            select(RawItem)
            .where(RawItem.source_id == source_id)
            .order_by(RawItem.published_at.desc(), RawItem.created_at.desc())
            .limit(limit)
        )
        raw_items = session.scalars(stmt).all()
        return [
            {
                "id": ri.id,
                "title": ri.title,
                "summary": ri.body,
                "url": ri.url,
                "metrics": ri.metrics_json,
                "published_at": ri.published_at.isoformat() if ri.published_at else None,
                "source_type": "raw",
            }
            for ri in raw_items
        ]

    cookie = get_cookie(session)

    if source_type == "hot_events":
        return fetch_hot_events(cookie, limit)
    if source_type == "hot_stocks":
        return fetch_hot_stocks(cookie, config, limit)
    if source_type == "screener":
        return fetch_screener(cookie, config, limit)

    if source_type == "eastmoney_sectors":
        return fetch_sectors(config, limit)
    if source_type == "eastmoney_gainers":
        return fetch_gainers(config, limit)
    if source_type == "eastmoney_losers":
        return fetch_losers(config, limit)
    if source_type == "eastmoney_industry":
        return fetch_industry(config, limit)
    if source_type == "eastmoney_indices":
        return fetch_indices(config, limit)
    if source_type == "eastmoney_capital_flow":
        return fetch_capital_flow(config, limit)
    if source_type == "eastmoney_announcements":
        return fetch_announcements(config, limit)

    if source_type == "tonghuashun_news":
        source_id = session.scalar(
            select(Source.id).where(Source.site == "tonghuashun").limit(1)
        )
        if source_id is None:
            return []
        stmt = (
            select(RawItem)
            .where(RawItem.source_id == source_id)
            .order_by(RawItem.published_at.desc(), RawItem.created_at.desc())
            .limit(limit)
        )
        news_items = session.scalars(stmt).all()
        return [
            {
                "id": ri.id,
                "title": ri.title,
                "summary": ri.body,
                "url": ri.url,
                "published_at": ri.published_at.isoformat() if ri.published_at else None,
                "source_type": "tonghuashun_news",
            }
            for ri in news_items
        ]

    return []


def get_page_blocks(session: Session, route: str) -> list[dict]:
    stmt = (
        select(PageBlock)
        .where(
            PageBlock.page_route == route,
            PageBlock.enabled.is_(True),
            PageBlock.status == "published",
        )
        .order_by(PageBlock.grid_y, PageBlock.grid_x, PageBlock.sort_order)
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
            "col_span": block.col_span,
            "row_span": block.row_span,
            "grid_x": block.grid_x,
            "grid_y": block.grid_y,
            "data": resolve_block_data(session, block),
        }
        result.append(item)
    return result
