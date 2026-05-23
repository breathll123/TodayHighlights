import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from sqlalchemy.orm import joinedload

from app.core.config import settings
from app.core.crypto import CryptoService
from app.models.entities import Highlight, PageBlock, Source


def _get_xueqiu_cookie(session: Session) -> str:
    source = session.scalar(select(Source).where(Source.site == "xueqiu").limit(1))
    if source is None:
        return ""
    return CryptoService(settings.app_secret_key).decrypt(source.cookie_encrypted)


def _fetch_hot_events(cookie: str, limit: int) -> list[dict]:
    try:
        resp = httpx.get(
            "https://xueqiu.com/hot_event/list.json",
            headers={"Cookie": cookie, "User-Agent": "Mozilla/5.0 DailyHighlights/0.1", "Accept": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        items = resp.json().get("list", [])[:limit]
        return [
            {
                "title": item.get("tag", "").strip("#"),
                "summary": item.get("content", ""),
                "tags": [item.get("tag", "").strip("#")],
                "score": item.get("status_count", 0),
                "source": "hot_events",
            }
            for item in items
        ]
    except Exception:
        return []


def _fetch_hot_stocks(cookie: str, config: dict, limit: int) -> list[dict]:
    try:
        stock_type = config.get("type", 10)
        resp = httpx.get(
            f"https://stock.xueqiu.com/v5/stock/hot_stock/list.json?type={stock_type}&size={limit}",
            headers={"Cookie": cookie, "User-Agent": "Mozilla/5.0 DailyHighlights/0.1", "Accept": "application/json", "Referer": "https://xueqiu.com/"},
            timeout=15,
        )
        resp.raise_for_status()
        items = resp.json().get("data", {}).get("items", [])
        return [
            {
                "title": f"{item.get('name', '')}",
                "summary": f"{item.get('code', '')} 热度{int(item.get('value', 0))} 变动{item.get('increment', 0)}",
                "symbols": [item.get("code", "")],
                "score": int(item.get("value", 0)),
                "source": "hot_stocks",
                "percent": item.get("percent", 0),
                "current": item.get("current", 0),
            }
            for item in items
        ]
    except Exception:
        return []


def _fetch_screener(cookie: str, config: dict, limit: int) -> list[dict]:
    try:
        order_by = config.get("order_by", "percent")
        resp = httpx.get(
            f"https://xueqiu.com/service/screener/quote/list?page=1&size={limit}&order=desc&order_by={order_by}&type=stock&exchange=CN&market=CN",
            headers={"Cookie": cookie, "User-Agent": "Mozilla/5.0 DailyHighlights/0.1", "Accept": "application/json", "Referer": "https://xueqiu.com/"},
            timeout=15,
        )
        resp.raise_for_status()
        items = resp.json().get("data", {}).get("list", [])
        return [
            {
                "title": f"{item.get('name', '')} ({item.get('symbol', '')})",
                "summary": f"价格 {item.get('current', 0)} 涨跌幅 {item.get('percent', 0):.2f}% 换手率 {item.get('turnover_rate', 0):.2f}% 市值 {item.get('market_capital', 0) / 1e8:.0f}亿",
                "symbols": [item.get("symbol", "")],
                "score": int(item.get("percent", 0) * 100),
                "source": "screener",
            }
            for item in items
        ]
    except Exception:
        return []


def _fetch_search(cookie: str, config: dict, limit: int) -> list[dict]:
    try:
        query = config.get("query", "")
        resp = httpx.get(
            f"https://xueqiu.com/statuses/search.json?q={query}&count={limit}",
            headers={"Cookie": cookie, "User-Agent": "Mozilla/5.0 DailyHighlights/0.1", "Accept": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        items = resp.json().get("list", [])
        return [
            {
                "title": item.get("title", ""),
                "summary": item.get("description", item.get("text", "")),
                "tags_json": [],
                "score": int(item.get("like_count", 0)) + int(item.get("view_count", 0) // 1000),
                "source": "search",
            }
            for item in items
        ]
    except Exception:
        return []


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

    cookie = _get_xueqiu_cookie(session)

    if source_type == "hot_events":
        return _fetch_hot_events(cookie, limit)

    if source_type == "hot_stocks":
        return _fetch_hot_stocks(cookie, config, limit)

    if source_type == "screener":
        return _fetch_screener(cookie, config, limit)

    if source_type == "search":
        return _fetch_search(cookie, config, limit)

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
