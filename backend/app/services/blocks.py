import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait
from contextvars import copy_context
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.logging import bind_log_context, log_event
from app.models.entities import AARankingDataset, Highlight, PageBlock, RawItem, Source
from app.services.adapters.xueqiu import (
    fetch_hot_events, fetch_hot_stocks, fetch_hot_stocks_cn,
    fetch_hot_stocks_hk, fetch_hot_stocks_us, fetch_screener, get_cookie,
)
from app.services.adapters.eastmoney import (
    fetch_announcements, fetch_capital_flow,
    fetch_indices, fetch_industry, fetch_sectors,
)

logger = logging.getLogger("today_highlights.blocks")

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


_DATA_UPDATED_FIELDS = ("data_updated_at", "updated_at", "generated_at", "created_at")

_SOURCE_ENTRY_URLS_BY_BLOCK_TYPE = {
    "eastmoney_sectors": "eastmoney://sectors",
    "eastmoney_industry": "eastmoney://industry",
    "eastmoney_capital_flow": "eastmoney://capital_flow",
    "eastmoney_indices": "eastmoney://indices",
    "eastmoney_longhu": "eastmoney://longhu",
    "tonghuashun_news": "tonghuashun://news",
    "aihot_news": "aihot://news",
    "qiumiwu_matches": "qiumiwu://matches",
    "qiumiwu_fixtures": "qiumiwu://matches",
    "qiumiwu_standings": "qiumiwu://matches",
    "qiumiwu_schedule": "qiumiwu://matches",
    "dongqiudi_matches": "dongqiudi://matches",
}

_SOURCE_SITES_BY_BLOCK_TYPE = {
    "hot_events": "xueqiu",
    "hot_stocks": "xueqiu",
    "xueqiu_hot_cn": "xueqiu",
    "xueqiu_hot_hk": "xueqiu",
    "xueqiu_hot_us": "xueqiu",
    "screener": "xueqiu",
}


def _parse_data_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _datetime_sort_key(value: datetime) -> float:
    if value.tzinfo is not None:
        return value.timestamp()
    return value.replace(tzinfo=timezone.utc).timestamp()


def _format_data_updated_at(value: datetime) -> str:
    if value.tzinfo is not None:
        value = value.replace(tzinfo=None)
    return value.replace(microsecond=0).isoformat(timespec="seconds")


def _infer_data_updated_at(data: list[dict], fallback: datetime | None = None) -> str | None:
    latest: datetime | None = None
    latest_key: float | None = None
    for item in data:
        if not isinstance(item, dict):
            continue
        for field in _DATA_UPDATED_FIELDS:
            parsed = _parse_data_datetime(item.get(field))
            if parsed is None:
                continue
            sort_key = _datetime_sort_key(parsed)
            if latest_key is None or sort_key > latest_key:
                latest = parsed
                latest_key = sort_key

    if latest is None:
        latest = fallback
    return _format_data_updated_at(latest) if latest is not None else None


def _published_aa_dataset_updated_at(session: Session, block: PageBlock) -> datetime | None:
    config = block.source_config or {}
    keys = config.get("dataset_keys")
    if not keys:
        single = config.get("dataset_key")
        keys = [single] if single else ["language_global"]
    keys = [str(key) for key in keys if key]
    if not keys:
        return None
    return session.scalar(
        select(func.max(AARankingDataset.published_at)).where(
            AARankingDataset.dataset_key.in_(keys),
            AARankingDataset.status == "published",
        )
    )


def _source_last_crawled_at(session: Session, block: PageBlock) -> datetime | None:
    config = block.source_config or {}
    if block.source_type == "raw":
        source_id = config.get("source_id")
        if source_id is None:
            return None
        return session.scalar(select(Source.last_crawled_at).where(Source.id == source_id).limit(1))

    if block.source_type == "topic":
        topic_id = config.get("topic_id")
        if topic_id is None:
            return None
        return session.scalar(
            select(func.max(Source.last_crawled_at)).where(Source.topic_id == topic_id)
        )

    if block.source_type == "artificial_analysis_ranking":
        return _published_aa_dataset_updated_at(session, block)

    entry_url = _SOURCE_ENTRY_URLS_BY_BLOCK_TYPE.get(block.source_type)
    if entry_url:
        return session.scalar(
            select(Source.last_crawled_at).where(Source.entry_url == entry_url).limit(1)
        )

    site = _SOURCE_SITES_BY_BLOCK_TYPE.get(block.source_type)
    if site:
        return session.scalar(
            select(func.max(Source.last_crawled_at)).where(Source.site == site)
        )

    return None


def _block_data_updated_at(session: Session, block: PageBlock, data: list[dict]) -> str | None:
    source_updated_at = _source_last_crawled_at(session, block)
    if source_updated_at is not None:
        return _format_data_updated_at(source_updated_at)
    return _infer_data_updated_at(data)


def _block_payload(block: PageBlock, data: list[dict], data_updated_at: str | None) -> dict:
    return {
        "id": block.id,
        "title": block.title,
        "sort_order": block.sort_order,
        "page_route": block.page_route,
        "display_style": block.display_style,
        "display_count": block.display_count,
        "source_type": block.source_type,
        "source_config": block.source_config or {},
        "col_span": block.col_span,
        "row_span": block.row_span,
        "grid_x": block.grid_x,
        "grid_y": block.grid_y,
        "data_updated_at": data_updated_at,
        "data": data,
    }


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
                "created_at": ri.created_at.isoformat() if ri.created_at else None,
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
        datacenter_item = RawItem.external_id.like(
            r"lhb\_" + "____-__-__" + r"\_%",
            escape="\\",
        )
        trade_date = func.substr(RawItem.external_id, 5, 10)
        latest_trade_date = session.scalar(
            select(func.max(trade_date)).where(
                RawItem.source_id == longhu_source_id,
                datacenter_item,
            )
        )
        if latest_trade_date is None:
            return []
        stmt = (
            select(RawItem)
            .where(
                RawItem.source_id == longhu_source_id,
                datacenter_item,
                trade_date == latest_trade_date,
            )
        )
        longhu_items = session.scalars(stmt).all()
        longhu_items.sort(
            key=lambda item: abs(float((item.metrics_json or {}).get("net_buy", 0) or 0)),
            reverse=True,
        )
        longhu_items = longhu_items[:limit]
        return [
            {
                "id": ri.id,
                "title": ri.title,
                "summary": ri.body,
                "url": ri.url,
                "symbols": [ri.metrics_json.get("symbol", "")] if ri.metrics_json else [],
                "score": int(abs(ri.metrics_json.get("net_buy", 0) or 0)) if ri.metrics_json else 0,
                "net_amount": ri.metrics_json.get("net_buy", 0) if ri.metrics_json else 0,
                "reason": ri.metrics_json.get("reason", "") if ri.metrics_json else "",
                "source_type": "eastmoney_longhu",
                "percent": ri.metrics_json.get("percent", 0) if ri.metrics_json else 0,
                "published_at": ri.published_at.isoformat() if ri.published_at else None,
                "created_at": ri.created_at.isoformat() if ri.created_at else None,
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
                "created_at": ri.created_at.isoformat() if ri.created_at else None,
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

    if source_type == "market_index_trends":
        from app.services.adapters.eastmoney import fetch_index_trends
        indices = fetch_index_trends(config, limit)
        # Transform to match public /market-indices shape (code, name, current, change_pct, etc.)
        return [
            {
                "code": idx.get("symbols", [""])[0] if idx.get("symbols") else "",
                "name": idx.get("title", ""),
                "current": idx.get("current", 0),
                "change_pct": idx.get("percent", 0),
                "change_amount": idx.get("change_amount", 0),
                "volume": idx.get("volume", 0),
                "turnover": idx.get("turnover", 0),
                "url": idx.get("url", ""),
                "trend": idx.get("trend"),
                "source_type": "market_index_trends",
            }
            for idx in indices
        ]

    if source_type == "artificial_analysis_ranking":
        if session is None:
            raise RuntimeError("artificial_analysis_ranking requires a database session")
        config = block.source_config or {}
        # Support both legacy single key and new multi-key config
        keys = config.get("dataset_keys")
        if not keys:
            single = config.get("dataset_key")
            keys = [single] if single else ["language_global"]
        from app.services.artificial_analysis.repository import get_published_ranking
        all_data: list[dict] = []
        for key in keys:
            data, _meta = get_published_ranking(session, str(key), block.display_count)
            for item in data:
                item["dataset_key"] = str(key)
            all_data.extend(data)
        return all_data

    return []


def _resolve_live_block(block: PageBlock, cookie: str | None, media_cache) -> list[dict]:
    with bind_log_context(
        block_id=block.id,
        block_title=block.title,
        page_route=block.page_route,
        source_type=block.source_type,
    ):
        return resolve_block_data(None, block, cookie, media_cache)


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
    except Exception as exc:
        log_event(
            logger,
            channel="application",
            category="block",
            event="block.media-cache.failed",
            level=logging.WARNING,
            route=route,
            error_type=type(exc).__name__,
        )

    # Separate DB-dependent blocks (topic, raw) from live-API blocks
    db_types = {"topic", "raw", "eastmoney_longhu", "tonghuashun_news", "artificial_analysis_ranking"}
    db_blocks = [b for b in blocks if b.source_type in db_types]
    live_blocks = [b for b in blocks if b.source_type not in db_types]

    # Resolve DB blocks sequentially (need session)
    items = []
    for b in db_blocks:
        data = resolve_block_data(session, b)
        items.append(_block_payload(b, data, _block_data_updated_at(session, b, data)))

    # Pre-fetch cookie for live blocks (may fail if key changed)
    try:
        cookie = get_cookie(session)
    except Exception as exc:
        cookie = None
        log_event(
            logger,
            channel="application",
            category="block",
            event="block.cookie.unavailable",
            level=logging.WARNING,
            route=route,
            error_type=type(exc).__name__,
        )

    # Resolve live-API blocks in parallel using shared executor
    if live_blocks:
        started_at = {b.id: time.perf_counter() for b in live_blocks}
        futures = {
            _get_executor().submit(
                copy_context().run,
                _resolve_live_block,
                b,
                cookie,
                media_cache,
            ): b
            for b in live_blocks
        }
        done, pending = wait(futures, timeout=15)
        for future in pending:
            b = futures[future]
            future.cancel()
            log_event(
                logger,
                channel="application",
                category="block",
                event="block.resolve.failed",
                level=logging.WARNING,
                block_id=b.id,
                block_title=b.title,
                page_route=b.page_route,
                source_type=b.source_type,
                route=route,
                reason="timeout",
                duration_ms=round((time.perf_counter() - started_at[b.id]) * 1000, 2),
            )
            items.append(_block_payload(b, [], None))
        for future in done:
            b = futures[future]
            data_updated_at = None
            try:
                data = future.result()
                data_updated_at = _block_data_updated_at(session, b, data)
            except Exception as exc:
                log_event(
                    logger,
                    channel="application",
                    category="block",
                    event="block.resolve.failed",
                    level=logging.WARNING,
                    block_id=b.id,
                    block_title=b.title,
                    page_route=b.page_route,
                    source_type=b.source_type,
                    route=route,
                    reason="exception",
                    error_type=type(exc).__name__,
                    duration_ms=round((time.perf_counter() - started_at[b.id]) * 1000, 2),
                )
                data = []
            items.append(_block_payload(b, data, data_updated_at))

    # Preserve original order
    block_order = {b.id: i for i, b in enumerate(blocks)}
    items.sort(key=lambda x: block_order.get(x["id"], 0))
    return items
