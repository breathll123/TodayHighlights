from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx

from app.core.cache import ttl_cache
from app.core.config import settings


_proxy = settings.eastmoney_proxy
_http = httpx.Client(
    timeout=15,
    headers={"User-Agent": "Mozilla/5.0 DailyHighlights/0.1", "Referer": "https://quote.eastmoney.com/"},
    mounts={"http://": httpx.HTTPTransport(proxy=_proxy), "https://": httpx.HTTPTransport(proxy=_proxy)} if _proxy else None,
)


@ttl_cache(30, swr=300)
def fetch_sectors(config: dict, limit: int) -> list[dict]:
    try:
        board_type = config.get("board_type", "concept")
        fs_map = {"concept": "m:90+t:3", "industry": "m:90+t:2", "region": "m:90+t:1"}
        fs = fs_map.get(board_type, "m:90+t:3")
        resp = _http.get(
            "https://push2delay.eastmoney.com/api/qt/clist/get",
            params={"pn": 1, "pz": limit, "po": 1, "np": 1, "fltt": 2, "invt": 2, "fid": "f3", "fs": fs,
                    "fields": "f2,f3,f4,f12,f14"},
        )
        resp.raise_for_status()
        items = resp.json().get("data", {}).get("diff", [])
        return [
            {
                "title": item.get("f14", ""),
                "summary": f"指数 {item.get('f2', 0):.2f} 涨跌幅 {item.get('f3', 0):.2f}%",
                "symbols": [item.get("f12", "")],
                "score": int(abs(item.get("f3", 0)) * 100),
                "source": "eastmoney_sectors",
                "percent": item.get("f3", 0),
                "url": f"https://quote.eastmoney.com/bk/90.{item.get('f12', '')}.html",
            }
            for item in items
        ]
    except Exception:
        return []


@ttl_cache(30, swr=300)
def fetch_longhu(config: dict, limit: int) -> list[dict]:
    try:
        resp = _http.get(
            "https://push2delay.eastmoney.com/api/qt/clist/get",
            params={"pn": 1, "pz": limit, "po": 1, "np": 1, "fltt": 2, "invt": 2, "fid": "f178",
                    "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
                    "fields": "f2,f3,f8,f12,f14,f152,f174,f175,f176,f177,f178,f179"},
        )
        resp.raise_for_status()
        items = resp.json().get("data", {}).get("diff", [])
        result = []
        for item in items:
            if item.get("f152") != 2:
                continue
            total_amt = abs(item.get("f178", 0) or 0) / 1e8
            buy_amt = abs(item.get("f174", 0) or 0) / 1e8
            sell_amt = abs(item.get("f176", 0) or 0) / 1e8
            result.append({
                "title": item.get("f14", ""),
                "summary": f"成交{total_amt:.1f}亿 买入{buy_amt:.1f}亿 卖出{sell_amt:.1f}亿",
                "symbols": [item.get("f12", "")],
                "score": int(total_amt),
                "source": "eastmoney_longhu",
                "percent": item.get("f3", 0),
                "current": item.get("f2", 0),
                "url": f"https://quote.eastmoney.com/{item.get('f12', '')}.html",
            })
            if len(result) >= limit:
                break
        return result
    except Exception:
        return []


def _fetch_top_stock(board_code: str) -> tuple[str, dict | None]:
    """Fetch the top stock from a single industry board. Thread-safe via shared _http client."""
    try:
        sr = _http.get(
            "https://push2delay.eastmoney.com/api/qt/clist/get",
            params={"pn": 1, "pz": 1, "po": 1, "np": 1, "fltt": 2, "invt": 2, "fid": "f3",
                    "fs": f"b:{board_code}", "fields": "f2,f3,f12,f14"},
        )
        sr.raise_for_status()
        items = sr.json().get("data", {}).get("diff", [])
        if items:
            return board_code, items[0]
    except Exception:
        pass
    return board_code, None


@ttl_cache(30, swr=600)
def fetch_industry(config: dict, limit: int) -> list[dict]:
    try:
        resp = _http.get(
            "https://push2delay.eastmoney.com/api/qt/clist/get",
            params={"pn": 1, "pz": limit, "po": 1, "np": 1, "fltt": 2, "invt": 2, "fid": "f3",
                    "fs": "m:90+t:2", "fields": "f2,f3,f4,f12,f14"},
        )
        resp.raise_for_status()
        boards = resp.json().get("data", {}).get("diff", [])

        # Fetch top stock from each board IN PARALLEL
        top_stocks: dict[str, dict] = {}
        board_codes = [b.get("f12", "") for b in boards[:limit]]

        if board_codes:
            with ThreadPoolExecutor(max_workers=min(len(board_codes), 8)) as pool:
                futures = [pool.submit(_fetch_top_stock, code) for code in board_codes]
                for future in as_completed(futures):
                    code, stock = future.result()
                    if stock is not None:
                        top_stocks[code] = stock

        result = []
        for item in boards:
            code = item.get("f12", "")
            ts = top_stocks.get(code)
            summary = f"指数 {item.get('f2', 0):.2f} 涨跌幅 {item.get('f3', 0):.2f}%"
            if ts:
                summary += f"  |  {ts['f14']} {ts['f3']:+.2f}%"
            result.append({
                "title": item.get("f14", ""),
                "summary": summary,
                "symbols": [code],
                "score": int(abs(item.get("f3", 0)) * 100),
                "source": "eastmoney_industry",
                "percent": item.get("f3", 0),
                "url": f"https://quote.eastmoney.com/bk/90.{code}.html",
            })
        return result
    except Exception:
        return []


@ttl_cache(30, swr=300)
def fetch_indices(_config: dict, limit: int) -> list[dict]:
    """指数行情 — 使用新浪财经 API，稳定不封 IP"""
    try:
        import re
        index_map = [
            ("s_sh000001", "000001"),
            ("s_sz399001", "399001"),
            ("s_sz399006", "399006"),
            ("s_sh000688", "000688"),
            ("s_sz399673", "399673"),
            ("s_sh000300", "000300"),
        ]
        codes = ",".join(c for c, _ in index_map[:limit])
        resp = httpx.get(
            f"https://hq.sinajs.cn/list={codes}",
            headers={"User-Agent": "Mozilla/5.0 DailyHighlights/0.1", "Referer": "https://finance.sina.com.cn/"},
            timeout=10,
        )
        resp.raise_for_status()
        text = resp.content.decode("gbk")
        result = []
        for symbol, code in index_map[:limit]:
            m = re.search(rf'hq_str_{symbol}="([^"]*)"', text)
            if not m:
                continue
            fields = m.group(1).split(",")
            if len(fields) < 4:
                continue
            name = fields[0]
            current = float(fields[1])
            percent = float(fields[3])
            result.append({
                "title": name,
                "summary": f"{current:.2f} {percent:+.2f}%",
                "symbols": [code],
                "score": int(abs(percent) * 100),
                "source": "eastmoney_indices",
                "percent": percent,
                "current": current,
                "url": f"https://quote.eastmoney.com/zs{code}.html",
            })
        return result
    except Exception:
        return []


@ttl_cache(30, swr=300)
def fetch_capital_flow(_config: dict, limit: int) -> list[dict]:
    try:
        resp = _http.get(
            "https://push2delay.eastmoney.com/api/qt/clist/get",
            params={"pn": 1, "pz": limit, "po": 1, "np": 1, "fltt": 2, "invt": 2, "fid": "f62",
                    "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
                    "fields": "f2,f3,f12,f14,f62,f64,f66"},
        )
        resp.raise_for_status()
        items = resp.json().get("data", {}).get("diff", [])
        return [
            {
                "title": item.get("f14", ""),
                "summary": f"{item.get('f12', '')} 主力净流入{(item.get('f62', 0) or 0) / 1e8:.1f}亿 超大单{(item.get('f64', 0) or 0) / 1e8:.1f}亿",
                "symbols": [item.get("f12", "")],
                "score": int(abs(item.get("f62", 0) or 0)),
                "source": "eastmoney_capital_flow",
                "percent": item.get("f3", 0),
                "url": f"https://quote.eastmoney.com/{item.get('f12', '')}.html",
            }
            for item in items
        ]
    except Exception:
        return []


@ttl_cache(60, swr=600)
def fetch_announcements(_config: dict, limit: int) -> list[dict]:
    try:
        resp = httpx.get(
            "https://np-anotice-stock.eastmoney.com/api/security/ann",
            params={"page_index": 1, "page_size": limit, "ann_type": "A",
                    "sort_name": "notice_date", "sort_type": "desc"},
            headers={"User-Agent": "Mozilla/5.0 DailyHighlights/0.1", "Referer": "https://data.eastmoney.com/"},
            timeout=15,
        )
        resp.raise_for_status()
        items = resp.json().get("data", {}).get("list", [])
        result = []
        for item in items:
            codes = item.get("codes", [])
            symbols = [c.get("stock_code", "") for c in codes] if isinstance(codes, list) else []
            art_code = item.get("art_code", "")
            result.append({
                "title": item.get("title", ""),
                "summary": f"{item.get('notice_date', '')} {', '.join(symbols[:3])}",
                "symbols": symbols,
                "score": 0,
                "source": "eastmoney_announcements",
                "url": f"https://data.eastmoney.com/notices/detail/{art_code}.html" if art_code else None,
            })
        return result
    except Exception:
        return []
