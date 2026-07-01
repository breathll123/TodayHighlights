import logging
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait
from contextvars import copy_context
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.logging import bind_log_context, log_event
from app.models.entities import (
    AARankingDataset, Highlight, PageBlock, RawItem, Skill, Source,
    GameItem, GameRawSnapshot, GameRanking, GameDeal
)
from app.services.adapters.xueqiu import (
    fetch_hot_events, fetch_hot_stocks, fetch_hot_stocks_cn,
    fetch_hot_stocks_hk, fetch_hot_stocks_us, fetch_screener, get_cookie,
)
from app.services.adapters.eastmoney import (
    fetch_announcements, fetch_capital_flow,
    fetch_indices, fetch_industry, fetch_sectors,
)
from app.services.adapters.game_steam import parse_steam_most_played_response

logger = logging.getLogger("today_highlights.blocks")

_GAME_RANKING_SOURCES = {
    "game_top_sellers": ("steam", "top_sellers"),
    "game_new_releases": ("steam", "new_releases"),
    "game_most_played": ("steam", "most_played"),
    "game_wegame_popular": ("wegame", "popular_this_week"),
    "game_wegame_weekly_sales": ("wegame", "this_week_most_purchase"),
    "game_wegame_discounts": ("wegame", "discounts"),
}

# Module-level shared executor — avoids per-request creation/destruction overhead
_BLOCK_EXECUTOR: ThreadPoolExecutor | None = None
_EXECUTOR_LOCK = threading.Lock()


def _decode_raw_snapshot_json(snapshot: GameRawSnapshot) -> dict:
    try:
        body = snapshot.response_body
        if isinstance(body, bytes):
            text = body.decode("utf-8", errors="replace")
        else:
            text = str(body or "")
        payload = json.loads(text)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


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
    # 中国大模型榜单已重构为全球榜单的实时读时投影，自身不再发布物化数据集。
    # 因此其区块新鲜度统一使用全球榜单（language_global）的发布时间进行判定。
    keys = ["language_global" if k == "language_china" else k for k in keys]
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

    if block.source_type == "github_skills":
        return session.scalar(select(func.max(Skill.last_synced_at)).where(Skill.source == "github"))

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
        "theme": block.theme,
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
    # Public football blocks should return text/data first; logo downloads are opt-in.
    if media_cache is not None and source_type.startswith("qiumiwu_") and config.get("eager_media_cache") is True:
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

    if source_type == "github_skills":
        stmt = (
            select(Skill)
            .where(Skill.source == "github", Skill.is_skill.is_(True), Skill.status == "active")
            .order_by(Skill.popularity.desc())
            .limit(limit)
        )
        skills = session.scalars(stmt).all()
        return [
            {
                "id": skill.id,
                "rank": index + 1,
                "title": skill.name,
                "owner": skill.author,
                "summary": skill.description_zh or skill.description,
                "url": skill.url,
                "score": skill.popularity,
                "source_type": "github_skills",
            }
            for index, skill in enumerate(skills)
        ]

    if source_type in _GAME_RANKING_SOURCES:
        provider, ranking_type = _GAME_RANKING_SOURCES[source_type]
        ranking_exists = (
            select(GameRanking.id)
            .where(GameRanking.snapshot_id == GameRawSnapshot.id)
            .exists()
        )
        deal_exists = (
            select(GameDeal.id)
            .where(GameDeal.snapshot_id == GameRawSnapshot.id)
            .exists()
        )
        detail_exists = or_(ranking_exists, deal_exists) if source_type == "game_top_sellers" else ranking_exists

        # 1. 查找最新一次有明细的抓取快照。只有原始快照但没有明细时，页面无法展示。
        latest_snap = session.scalar(
            select(GameRawSnapshot)
            .where(
                GameRawSnapshot.provider == provider,
                GameRawSnapshot.endpoint_key == ranking_type,
                GameRawSnapshot.parse_status != "failed",
                detail_exists,
            )
            .order_by(GameRawSnapshot.captured_at.desc())
            .limit(1)
        )
        if latest_snap is None:
            if source_type == "game_most_played":
                raw_snap = session.scalar(
                    select(GameRawSnapshot)
                    .where(
                        GameRawSnapshot.provider == "steam",
                        GameRawSnapshot.endpoint_key == "most_played",
                        GameRawSnapshot.status_code == 200,
                    )
                    .order_by(GameRawSnapshot.captured_at.desc())
                    .limit(1)
                )
                if raw_snap is not None:
                    raw_items = parse_steam_most_played_response(_decode_raw_snapshot_json(raw_snap), limit=limit)
                    return [
                        {
                            "id": f"most_played_raw_{item['external_id']}",
                            "title": item["name"],
                            "subtitle": "Steam",
                            "rank": item["rank"],
                            "score": float(item["score"]) if item.get("score") is not None else None,
                            "provider": "steam",
                            "source": "Steam",
                            "external_id": item["external_id"],
                            "url": item["source_url"],
                            "cover_url": item["cover_url"],
                            "cover_local": "",
                            "current_price": None,
                            "original_price": None,
                            "discount_percent": 0,
                            "discount_label": "",
                            "release_date": None,
                            "peak_in_game": item["metadata"].get("peak_in_game"),
                            "last_week_rank": item["metadata"].get("last_week_rank"),
                            "captured_at": raw_snap.captured_at.isoformat(),
                            "created_at": raw_snap.created_at.isoformat(),
                            "source_type": source_type,
                        }
                        for item in raw_items[:limit]
                    ]
            return []

        # 2. 查询快照对应的排行数据
        stmt = (
            select(GameRanking, GameItem)
            .join(GameItem, GameRanking.game_item_id == GameItem.id)
            .where(GameRanking.snapshot_id == latest_snap.id)
            .order_by(GameRanking.rank.asc())
            .limit(limit)
        )
        results = session.execute(stmt).all()
        if not results and source_type == "game_top_sellers":
            deal_stmt = (
                select(GameDeal, GameItem)
                .join(GameItem, GameDeal.game_item_id == GameItem.id)
                .where(GameDeal.snapshot_id == latest_snap.id)
                .order_by(GameDeal.id.asc())
                .limit(limit)
            )
            deal_results = session.execute(deal_stmt).all()
            return [
                {
                    "id": deal.id,
                    "title": item.name,
                    "subtitle": "Steam",
                    "rank": index + 1,
                    "score": None,
                    "provider": item.provider,
                    "source": "Steam",
                    "external_id": item.external_id,
                    "url": item.source_url,
                    "cover_url": item.cover_url,
                    "cover_local": item.cover_local,
                    "current_price": float(deal.current_price) if deal.current_price is not None else None,
                    "original_price": float(deal.original_price) if deal.original_price is not None else None,
                    "discount_percent": deal.discount_percent,
                    "discount_label": deal.discount_label,
                    "release_date": item.release_date.isoformat() if item.release_date else None,
                    "peak_in_game": None,
                    "last_week_rank": None,
                    "captured_at": deal.captured_at.isoformat(),
                    "created_at": deal.created_at.isoformat(),
                    "source_type": source_type,
                }
                for index, (deal, item) in enumerate(deal_results)
            ]
        if not results:
            return []

        # 提取 item id 用于批量查价格，避免 N+1 查询
        item_ids = [item.id for ranking, item in results]

        # 3. 批量拉取这批游戏的最新特惠价格快照
        deals_map = {}
        if item_ids:
            deal_stmt = select(GameDeal).where(GameDeal.snapshot_id == latest_snap.id, GameDeal.game_item_id.in_(item_ids))
            deals = session.scalars(deal_stmt).all()
            deals_map = {d.game_item_id: d for d in deals}

            # 兜底查询其他最新价格记录
            missing_ids = [iid for iid in item_ids if iid not in deals_map]
            for m_id in missing_ids:
                latest_deal = session.scalar(
                    select(GameDeal)
                    .where(GameDeal.game_item_id == m_id)
                    .order_by(GameDeal.captured_at.desc())
                    .limit(1)
                )
                if latest_deal:
                    deals_map[m_id] = latest_deal

        # 4. 组装前端数据
        data_list = []
        for ranking, item in results:
            deal = deals_map.get(item.id)
            metadata = item.metadata_json or {}
            source_label = "WeGame" if item.provider == "wegame" else "Steam"
            data_list.append({
                "id": ranking.id,
                "title": item.name,
                "subtitle": source_label,
                "rank": ranking.rank,
                "score": float(ranking.score) if ranking.score is not None else None,
                "provider": item.provider,
                "source": source_label,
                "external_id": item.external_id,
                "url": item.source_url,
                "cover_url": item.cover_url,
                "cover_local": item.cover_local,
                "current_price": float(deal.current_price) if (deal and deal.current_price is not None) else None,
                "original_price": float(deal.original_price) if (deal and deal.original_price is not None) else None,
                "discount_percent": deal.discount_percent if deal else 0,
                "discount_label": deal.discount_label if deal else "",
                "release_date": item.release_date.isoformat() if item.release_date else None,
                "peak_in_game": metadata.get("peak_in_game"),
                "last_week_rank": metadata.get("last_week_rank"),
                "summary": metadata.get("description_zh") or metadata.get("comments") or metadata.get("description_original") or "",
                "e_game_name": metadata.get("e_game_name") or "",
                "last_purchase_rank": metadata.get("last_purchase_rank"),
                "week_recommend_ratio": metadata.get("week_recommend_ratio"),
                "month_recommend_ratio": metadata.get("month_recommend_ratio"),
                "total_recommend_ratio": metadata.get("total_recommend_ratio"),
                "captured_at": ranking.captured_at.isoformat(),
                "created_at": ranking.created_at.isoformat(),
                "source_type": source_type,
            })
        return data_list

    if source_type == "game_specials":
        # 1. 查找最新一次的打折特惠快照
        latest_snap = session.scalar(
            select(GameRawSnapshot)
            .join(GameDeal, GameDeal.snapshot_id == GameRawSnapshot.id)
            .where(
                GameRawSnapshot.provider == "steam",
                GameRawSnapshot.endpoint_key == "specials",
                GameRawSnapshot.parse_status != "failed",
            )
            .order_by(GameRawSnapshot.captured_at.desc())
            .limit(1)
        )
        if latest_snap is None:
            return []

        # 2. 查询对应的打折特惠详情（依折扣从大到小排序）
        stmt = (
            select(GameDeal, GameItem)
            .join(GameItem, GameDeal.game_item_id == GameItem.id)
            .where(GameDeal.snapshot_id == latest_snap.id)
            .order_by(GameDeal.discount_percent.desc(), GameDeal.id.asc())
            .limit(limit)
        )
        results = session.execute(stmt).all()

        # 3. 组装前端数据
        return [
            {
                "id": deal.id,
                "title": item.name,
                "subtitle": "Steam",
                "rank": index + 1,
                "provider": item.provider,
                "source": "Steam",
                "external_id": item.external_id,
                "url": deal.deal_url,
                "cover_url": item.cover_url,
                "cover_local": item.cover_local,
                "current_price": float(deal.current_price) if deal.current_price is not None else None,
                "original_price": float(deal.original_price) if deal.original_price is not None else None,
                "discount_percent": deal.discount_percent,
                "discount_label": deal.discount_label,
                "release_date": item.release_date.isoformat() if item.release_date else None,
                "captured_at": deal.captured_at.isoformat(),
                "created_at": deal.created_at.isoformat(),
                "source_type": "game_specials",
            }
            for index, (deal, item) in enumerate(results)
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
    db_types = {
        "topic", "raw", "eastmoney_longhu", "tonghuashun_news", "artificial_analysis_ranking",
        "github_skills", "game_top_sellers", "game_specials", "game_new_releases", "game_most_played",
        "game_wegame_popular", "game_wegame_weekly_sales", "game_wegame_discounts",
    }
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
