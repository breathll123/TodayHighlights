import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.entities import Highlight, PageBlock, RawItem, Source
from app.services.adapters.xueqiu import (
    fetch_hot_events, fetch_hot_stocks, fetch_hot_stocks_cn,
    fetch_hot_stocks_hk, fetch_hot_stocks_us, fetch_screener, get_cookie,
)
from app.services.adapters.eastmoney import (
    fetch_announcements, fetch_capital_flow,
    fetch_indices, fetch_industry, fetch_sectors,
)

logger = logging.getLogger(__name__)

# Module-level shared executor — avoids per-request creation/destruction overhead
_BLOCK_EXECUTOR: ThreadPoolExecutor | None = None
_EXECUTOR_LOCK = threading.Lock()


def _get_executor() -> ThreadPoolExecutor:
    """Get or create the shared block executor. Recreates after shutdown (test resilience)."""
    global _BLOCK_EXECUTOR
    if _BLOCK_EXECUTOR is None or _BLOCK_EXECUTOR._shutdown:
        with _EXECUTOR_LOCK:
            if _BLOCK_EXECUTOR is None or _BLOCK_EXECUTOR._shutdown:
                _BLOCK_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="block-resolve")
    return _BLOCK_EXECUTOR


def shutdown_executor():
    """Called during app shutdown."""
    global _BLOCK_EXECUTOR
    if _BLOCK_EXECUTOR is not None:
        _BLOCK_EXECUTOR.shutdown(wait=False)
        _BLOCK_EXECUTOR = None


def resolve_block_data(
    session: Session | None,
    block: PageBlock,
    cookie: str | None = None,
    media_cache=None,
) -> list[dict]:
    source_type = block.source_type
    config = block.source_config or {}
    if media_cache is not None and source_type.startswith("qiumiwu_"):
        config = {**config, "_media_cache": media_cache}
    limit = block.display_count

    if source_type == "topic":
        topic_id = config.get("topic_id", 1)
        order_col = Highlight.score.desc() if block.sort_by != "created_at" else Highlight.created_at.desc()
        stmt = (
            select(Highlight)
            .options(joinedload(Highlight.raw_item))
            .where(Highlight.topic_id == topic_id, Highlight.is_hidden.is_(False))
            .order_by(Highlight.is_pinned.desc(), order_col, Highlight.created_at.desc())
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
        order_col = RawItem.published_at.desc() if block.sort_by != "created_at" else RawItem.created_at.desc()
        stmt = (
            select(RawItem)
            .where(RawItem.source_id == source_id)
            .order_by(order_col, RawItem.created_at.desc())
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

    if cookie is None:
        cookie = get_cookie(session)

    if source_type == "hot_events":
        return fetch_hot_events(cookie, limit)
    if source_type == "hot_stocks":
        return fetch_hot_stocks(cookie, config, limit)
    if source_type == "xueqiu_hot_cn":
        return fetch_hot_stocks_cn(cookie, config, limit)
    if source_type == "xueqiu_hot_hk":
        return fetch_hot_stocks_hk(cookie, config, limit)
    if source_type == "xueqiu_hot_us":
        return fetch_hot_stocks_us(cookie, config, limit)
    if source_type == "screener":
        return fetch_screener(cookie, config, limit)

    if source_type == "eastmoney_sectors":
        return fetch_sectors(config, limit)
    if source_type == "eastmoney_longhu":
        longhu_source_id = session.scalar(select(Source.id).where(Source.entry_url == "eastmoney://longhu").limit(1))
        if longhu_source_id is None:
            return []
        stmt = (
            select(RawItem)
            .where(RawItem.source_id == longhu_source_id)
            .order_by(RawItem.published_at.desc(), RawItem.created_at.desc())
            .limit(limit)
        )
        longhu_items = session.scalars(stmt).all()
        return [
            {
                "id": ri.id,
                "title": ri.title,
                "summary": ri.body,
                "url": ri.url,
                "symbols": [ri.metrics_json.get("symbol", "")] if ri.metrics_json else [],
                "score": int(abs(ri.metrics_json.get("net_buy", 0) or 0)) if ri.metrics_json else 0,
                "source_type": "eastmoney_longhu",
                "percent": ri.metrics_json.get("percent", 0) if ri.metrics_json else 0,
            }
            for ri in longhu_items
        ]
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

    # Create media cache for football adapters (session may be None for live blocks)
    if source_type == "qiumiwu_matches":
        from app.services.adapters.qiumiwu import fetch_matches
        return fetch_matches(config, limit)

    if source_type == "qiumiwu_fixtures":
        from app.services.adapters.qiumiwu import fetch_fixtures
        return fetch_fixtures(config, limit)

    if source_type == "qiumiwu_schedule":
        from app.services.adapters.qiumiwu_schedule import fetch_competition_schedule
        return fetch_competition_schedule(config, limit)

    if source_type == "qiumiwu_standings":
        from app.services.adapters.qiumiwu import fetch_standings
        return fetch_standings(config, max(limit, 1000))

    if source_type == "datalearner_leaderboard":
        from app.services.adapters.datalearner import fetch_leaderboard
        return fetch_leaderboard(config, limit)

    if source_type == "datalearner_aa_index":
        from app.services.adapters.datalearner import fetch_aa_index
        return fetch_aa_index(config, max(limit, 500))

    if source_type == "aihot_news":
        from app.services.adapters.aihot import fetch_news
        return fetch_news(config, limit)

    if source_type == "artificial_analysis_ranking":
        if session is None:
            raise RuntimeError("artificial_analysis_ranking requires a database session")
        config = block.source_config or {}
        dataset_key = str(config.get("dataset_key") or "language_global")
        from app.services.artificial_analysis.repository import get_published_ranking
        data, _meta = get_published_ranking(session, dataset_key, block.display_count)
        return data

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

    media_cache = None
    try:
        from app.services.media_cache import MediaCacheService
        media_cache = MediaCacheService(session)
    except Exception:
        pass

    # Separate DB-dependent blocks (topic, raw) from live-API blocks
    db_types = {"topic", "raw", "eastmoney_longhu", "tonghuashun_news", "artificial_analysis_ranking"}
    db_blocks = [b for b in blocks if b.source_type in db_types]
    live_blocks = [b for b in blocks if b.source_type not in db_types]

    # Resolve DB blocks sequentially (need session)
    items = []
    for b in db_blocks:
        items.append({
            "id": b.id, "title": b.title, "sort_order": b.sort_order,
            "page_route": b.page_route,
            "display_style": b.display_style, "display_count": b.display_count,
            "source_type": b.source_type, "source_config": b.source_config or {},
            "col_span": b.col_span, "row_span": b.row_span,
            "grid_x": b.grid_x, "grid_y": b.grid_y,
            "data": resolve_block_data(session, b),
        })

    # Pre-fetch cookie for live blocks (may fail if key changed)
    try:
        cookie = get_cookie(session)
    except Exception:
        cookie = None

    # Resolve live-API blocks in parallel using shared executor
    if live_blocks:
        futures = {_get_executor().submit(resolve_block_data, None, b, cookie, media_cache): b for b in live_blocks}
        for future in as_completed(futures):
            b = futures[future]
            try:
                data = future.result(timeout=15)
            except TimeoutError:
                logger.warning("Block %s (type=%s) timed out after 15s", b.id, b.source_type)
                data = []
            except Exception:
                logger.warning("Block %s (type=%s) failed", b.id, b.source_type, exc_info=True)
                data = []
            items.append({
                "id": b.id, "title": b.title, "sort_order": b.sort_order,
                "page_route": b.page_route,
                "display_style": b.display_style, "display_count": b.display_count,
                "source_type": b.source_type, "source_config": b.source_config or {},
                "col_span": b.col_span, "row_span": b.row_span,
                "grid_x": b.grid_x, "grid_y": b.grid_y,
                "data": data,
            })

    # Preserve original order
    block_order = {b.id: i for i, b in enumerate(blocks)}
    items.sort(key=lambda x: block_order.get(x["id"], 0))
    return items
