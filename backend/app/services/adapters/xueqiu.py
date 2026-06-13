import base64

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.cache import ttl_cache
from app.core.config import settings
from app.core.crypto import CryptoService
from app.core.logging import log_adapter_failure, observed_http_get
from app.models.entities import Source


@ttl_cache(300, shared=False)
def _decrypt_cookie(cookie_encrypted: str) -> str:
    """Cached decryption of xueqiu cookie. Keyed on encrypted string."""
    if not cookie_encrypted:
        return ""
    return CryptoService(settings.app_secret_key).decrypt(cookie_encrypted)


def get_cookie(session: Session) -> str:
    encrypted = session.scalar(
        select(Source.cookie_encrypted).where(Source.site == "xueqiu").limit(1)
    )
    if not encrypted:
        return ""
    return _decrypt_cookie(encrypted)


@ttl_cache(30, swr=300)
def fetch_hot_events(cookie: str, limit: int) -> list[dict]:
    try:
        resp = observed_http_get(
            httpx.get,
            "https://xueqiu.com/hot_event/list.json",
            provider="xueqiu", operation="hot_events",
            host="xueqiu.com", path="/hot_event/list.json",
            headers={"Cookie": cookie, "User-Agent": "Mozilla/5.0 TodayHighlights/0.1", "Accept": "application/json", "Referer": "https://xueqiu.com/"},
            timeout=15,
        )
        resp.raise_for_status()
        items = resp.json().get("list", [])[:limit]
        return [
            {
                "title": item.get("tag", "").strip("#"),
                "summary": item.get("content", ""),
                "url": f"https://xueqiu.com/hashtag/{base64.urlsafe_b64encode(item.get('tag', '').encode()).decode().rstrip('=')}",
                "tags": [item.get("tag", "").strip("#")],
                "score": item.get("status_count", 0) + (100 if item.get("hot") else 0),
                "source": "hot_events",
            }
            for item in items
        ]
    except Exception as exc:
        log_adapter_failure(provider="xueqiu", operation="hot_events", stage="parse", exc=exc)
        return []


@ttl_cache(30, swr=300)
def fetch_hot_stocks(cookie: str, config: dict, limit: int) -> list[dict]:
    try:
        stock_type = config.get("type", 10)
        resp = observed_http_get(
            httpx.get,
            f"https://stock.xueqiu.com/v5/stock/hot_stock/list.json?type={stock_type}&size={limit}",
            provider="xueqiu", operation="hot_stocks",
            host="stock.xueqiu.com", path="/v5/stock/hot_stock/list.json",
            headers={"Cookie": cookie, "User-Agent": "Mozilla/5.0 TodayHighlights/0.1", "Accept": "application/json", "Referer": "https://xueqiu.com/"},
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
    except Exception as exc:
        log_adapter_failure(provider="xueqiu", operation="hot_stocks", stage="parse", exc=exc)
        return []


@ttl_cache(30, swr=300)
def fetch_hot_stocks_cn(cookie: str, config: dict, limit: int) -> list[dict]:
    return _fetch_hot_stocks_typed(cookie, 12, "xueqiu_hot_cn", limit)


@ttl_cache(30, swr=300)
def fetch_hot_stocks_hk(cookie: str, config: dict, limit: int) -> list[dict]:
    return _fetch_hot_stocks_typed(cookie, 13, "xueqiu_hot_hk", limit)


@ttl_cache(30, swr=300)
def fetch_hot_stocks_us(cookie: str, config: dict, limit: int) -> list[dict]:
    return _fetch_hot_stocks_typed(cookie, 11, "xueqiu_hot_us", limit)


def _fetch_hot_stocks_typed(cookie: str, stock_type: int, source: str, limit: int) -> list[dict]:
    try:
        resp = observed_http_get(
            httpx.get,
            f"https://stock.xueqiu.com/v5/stock/hot_stock/list.json?type={stock_type}&size={limit}",
            provider="xueqiu", operation=source,
            host="stock.xueqiu.com", path="/v5/stock/hot_stock/list.json",
            headers={"Cookie": cookie, "User-Agent": "Mozilla/5.0 TodayHighlights/0.1", "Accept": "application/json", "Referer": "https://xueqiu.com/"},
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
                "source": source,
                "percent": item.get("percent", 0),
                "current": item.get("current", 0),
                "url": f"https://xueqiu.com/S/{item.get('symbol', item.get('code', ''))}",
            }
            for item in items
        ]
    except Exception as exc:
        log_adapter_failure(provider="xueqiu", operation=source, stage="parse", exc=exc)
        return []


@ttl_cache(30, swr=300)
def fetch_screener(cookie: str, config: dict, limit: int) -> list[dict]:
    try:
        order_by = config.get("order_by", "percent")
        resp = observed_http_get(
            httpx.get,
            f"https://xueqiu.com/service/screener/quote/list?page=1&size={limit}&order=desc&order_by={order_by}&type=stock&exchange=CN&market=CN",
            provider="xueqiu", operation="screener",
            host="xueqiu.com", path="/service/screener/quote/list",
            headers={"Cookie": cookie, "User-Agent": "Mozilla/5.0 TodayHighlights/0.1", "Accept": "application/json", "Referer": "https://xueqiu.com/"},
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
    except Exception as exc:
        log_adapter_failure(provider="xueqiu", operation="screener", stage="parse", exc=exc)
        return []
