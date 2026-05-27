import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.cache import ttl_cache
from app.core.config import settings
from app.core.crypto import CryptoService
from app.models.entities import Source


def get_cookie(session: Session) -> str:
    source = session.scalar(select(Source).where(Source.site == "xueqiu").limit(1))
    if source is None:
        return ""
    return CryptoService(settings.app_secret_key).decrypt(source.cookie_encrypted)


@ttl_cache(30)
def fetch_hot_events(cookie: str, limit: int) -> list[dict]:
    try:
        resp = httpx.get(
            "https://xueqiu.com/hot_event/list.json",
            headers={"Cookie": cookie, "User-Agent": "Mozilla/5.0 DailyHighlights/0.1", "Accept": "application/json", "Referer": "https://xueqiu.com/"},
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


@ttl_cache(30)
def fetch_hot_stocks(cookie: str, config: dict, limit: int) -> list[dict]:
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
                "url": f"https://xueqiu.com/S/{item.get('symbol', item.get('code', ''))}",
            }
            for item in items
        ]
    except Exception:
        return []


@ttl_cache(30)
def fetch_screener(cookie: str, config: dict, limit: int) -> list[dict]:
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
                "percent": item.get("percent", 0),
                "url": f"https://xueqiu.com/S/{item.get('symbol', '')}",
            }
            for item in items
        ]
    except Exception:
        return []
