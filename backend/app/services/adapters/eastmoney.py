from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx

from app.core.cache import ttl_cache
from app.core.config import settings
from app.core.logging import log_adapter_failure, observed_http_get


_proxy = settings.eastmoney_proxy
_http = httpx.Client(
    timeout=15,
    headers={"User-Agent": "Mozilla/5.0 TodayHighlights/0.1", "Referer": "https://quote.eastmoney.com/"},
    mounts={"http://": httpx.HTTPTransport(proxy=_proxy), "https://": httpx.HTTPTransport(proxy=_proxy)} if _proxy else None,
)


@ttl_cache(30, swr=300)
def fetch_sectors(config: dict, limit: int) -> list[dict]:
    try:
        board_type = config.get("board_type", "concept")
        fs_map = {"concept": "m:90+t:3", "industry": "m:90+t:2", "region": "m:90+t:1"}
        fs = fs_map.get(board_type, "m:90+t:3")
        resp = observed_http_get(
            _http.get,
            "https://push2delay.eastmoney.com/api/qt/clist/get",
            provider="eastmoney", operation="sectors",
            host="push2delay.eastmoney.com", path="/api/qt/clist/get",
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
    except Exception as exc:
        log_adapter_failure(provider="eastmoney", operation="sectors", stage="parse", exc=exc)
        return []


@ttl_cache(30, swr=300)
def fetch_longhu(config: dict, limit: int) -> list[dict]:
    try:
        resp = observed_http_get(
            _http.get,
            "https://push2delay.eastmoney.com/api/qt/clist/get",
            provider="eastmoney", operation="longhu",
            host="push2delay.eastmoney.com", path="/api/qt/clist/get",
            params={"pn": 1, "pz": limit, "po": 1, "np": 1, "fltt": 2, "invt": 2, "fid": "f178",
                    "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
                    "fields": "f2,f3,f6,f8,f12,f14,f152,f174,f175,f176,f177,f178,f179,f190"},
        )
        resp.raise_for_status()
        items = resp.json().get("data", {}).get("diff", [])
        result = []
        for item in items:
            if item.get("f152") != 2:
                continue
            trade_amt = abs(item.get("f6", 0) or 0) / 1e8   # 成交额 (f6)
            buy_amt = abs(item.get("f174", 0) or 0) / 1e8    # 买方金额
            sell_amt = abs(item.get("f176", 0) or 0) / 1e8   # 卖方金额
            net_buy = (item.get("f178", 0) or 0) / 1e8       # 净买额 (正=净买, 负=净卖)
            result.append({
                "title": item.get("f14", ""),
                "summary": f"成交{trade_amt:.1f}亿 净买{net_buy:+.1f}亿 买入{buy_amt:.1f}亿 卖出{sell_amt:.1f}亿",
                "symbols": [item.get("f12", "")],
                "score": int(abs(item.get("f178", 0) or 0) / 1e8),
                "source": "eastmoney_longhu",
                "percent": item.get("f3", 0),
                "current": item.get("f2", 0),
                "url": f"https://quote.eastmoney.com/{item.get('f12', '')}.html",
            })
            if len(result) >= limit:
                break
        return result
    except Exception as exc:
        log_adapter_failure(provider="eastmoney", operation="longhu", stage="parse", exc=exc)
        return []


def _fetch_top_stock(board_code: str) -> tuple[str, dict | None]:
    """Fetch the top stock from a single industry board. Thread-safe via shared _http client."""
    try:
        sr = observed_http_get(
            _http.get,
            "https://push2delay.eastmoney.com/api/qt/clist/get",
            provider="eastmoney", operation="industry_top_stock",
            host="push2delay.eastmoney.com", path="/api/qt/clist/get",
            params={"pn": 1, "pz": 1, "po": 1, "np": 1, "fltt": 2, "invt": 2, "fid": "f3",
                    "fs": f"b:{board_code}", "fields": "f2,f3,f12,f14"},
        )
        sr.raise_for_status()
        items = sr.json().get("data", {}).get("diff", [])
        if items:
            return board_code, items[0]
    except Exception as exc:
        log_adapter_failure(provider="eastmoney", operation="industry_top_stock", stage="parse", exc=exc)
    return board_code, None


@ttl_cache(30, swr=600)
def fetch_industry(config: dict, limit: int) -> list[dict]:
    try:
        resp = observed_http_get(
            _http.get,
            "https://push2delay.eastmoney.com/api/qt/clist/get",
            provider="eastmoney", operation="industry",
            host="push2delay.eastmoney.com", path="/api/qt/clist/get",
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
    except Exception as exc:
        log_adapter_failure(provider="eastmoney", operation="industry", stage="parse", exc=exc)
        return []


@ttl_cache(30, swr=300)
def fetch_indices(_config: dict, limit: int) -> list[dict]:
    """指数行情快照 — 东方财富 push2delay 接口。"""
    index_map = [
        ("000001", "1.000001"),   # 上证指数
        ("399001", "0.399001"),   # 深证成指
        ("399006", "0.399006"),   # 创业板指
        ("000688", "1.000688"),   # 科创50
        ("399673", "0.399673"),   # 创业板50
        ("000300", "1.000300"),   # 沪深300
    ][:limit]

    try:
        resp = observed_http_get(
            _http.get,
            "https://push2delay.eastmoney.com/api/qt/ulist.np/get",
            provider="eastmoney",
            operation="indices",
            host="push2delay.eastmoney.com",
            path="/api/qt/ulist.np/get",
            params={
                "fltt": 2,
                "invt": 2,
                "fields": "f2,f3,f4,f5,f6,f12,f13,f14",
                "secids": ",".join(secid for _, secid in index_map),
            },
        )
        resp.raise_for_status()
    except Exception as exc:
        log_adapter_failure(provider="eastmoney", operation="indices", stage="request", exc=exc)
        return []

    try:
        items = resp.json().get("data", {}).get("diff", [])
        secid_by_code = {code: secid for code, secid in index_map}
        result = []
        for item in items:
            code = str(item.get("f12") or "")
            em_secid = secid_by_code.get(code)
            if em_secid is None:
                continue
            name = str(item.get("f14") or "")
            current = float(item.get("f2") or 0)
            percent = float(item.get("f3") or 0)
            change_amount = float(item.get("f4") or 0)
            volume = int(item.get("f5") or 0)
            turnover = float(item.get("f6") or 0)
            result.append({
                "title": name,
                "summary": f"{current:.2f} {percent:+.2f}%",
                "symbols": [code],
                "score": int(abs(percent) * 100),
                "source": "eastmoney_indices",
                "percent": percent,
                "current": current,
                "change_amount": change_amount,
                "volume": volume,
                "turnover": turnover,
                "em_secid": em_secid,
                "url": f"https://quote.eastmoney.com/zs{code}.html",
            })
        return result
    except Exception as exc:
        log_adapter_failure(provider="eastmoney", operation="indices", stage="parse", exc=exc)
        return []


@ttl_cache(60, swr=300)
def fetch_index_trends(_config: dict, limit: int) -> list[dict]:
    """指数分时趋势 — 东方财富 trends2 接口，256 个分时点"""
    snapshots = fetch_indices(_config, limit)
    if not snapshots:
        return []

    # Fetch trends in parallel
    trend_by_secid: dict[str, dict | None] = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {}
        for s in snapshots:
            secid = s.get("em_secid")
            if secid:
                futures[pool.submit(_fetch_one_trend, s)] = secid

        for future in as_completed(futures):
            secid = futures[future]
            try:
                trend_by_secid[secid] = future.result(timeout=3)
            except Exception as exc:
                log_adapter_failure(provider="eastmoney", operation="index_trend", stage="parse", exc=exc)
                trend_by_secid[secid] = None

    # Reassemble in original snapshot order
    trends_data = []
    for s in snapshots:
        item = dict(s)
        item["trend"] = trend_by_secid.get(s.get("em_secid", ""))
        trends_data.append(item)

    return trends_data


def _fetch_one_trend(snapshot: dict) -> dict | None:
    """Fetch intraday trend for a single index."""
    try:
        resp = observed_http_get(
            _http.get,
            "https://push2delay.eastmoney.com/api/qt/stock/trends2/get",
            provider="eastmoney", operation="index_trend",
            host="push2delay.eastmoney.com", path="/api/qt/stock/trends2/get",
            params={
                "fields1": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13",
                "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
                "secid": snapshot["em_secid"],
                "ndays": 1,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        raw = data.get("data")
        if not raw:
            return None
        trends = raw.get("trends", [])
        if not trends:
            return None
        trend_date = ""
        points = []
        highs = []
        lows = []
        for row in trends:
            parts = row.split(",")
            if len(parts) >= 3:
                full_time = parts[0]
                if " " in full_time and not trend_date:
                    trend_date = full_time.split(" ")[0]
                price = float(parts[2])
                points.append({
                    "time": full_time.split(" ")[-1][:5] if " " in full_time else full_time,
                    "price": price,
                })
                if len(parts) >= 5:
                    highs.append(float(parts[3]))
                    lows.append(float(parts[4]))
                else:
                    highs.append(price)
                    lows.append(price)
        return {
            "prev_close": raw.get("preClose", 0),
            "date": trend_date,
            "points": points,
            "high": max(highs) if highs else 0,
            "low": min(lows) if lows else 0,
        }
    except Exception as exc:
        log_adapter_failure(provider="eastmoney", operation="index_trend", stage="parse", exc=exc)
        return None


@ttl_cache(30, swr=300)
def fetch_capital_flow(_config: dict, limit: int) -> list[dict]:
    try:
        resp = observed_http_get(
            _http.get,
            "https://push2delay.eastmoney.com/api/qt/clist/get",
            provider="eastmoney", operation="capital_flow",
            host="push2delay.eastmoney.com", path="/api/qt/clist/get",
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
    except Exception as exc:
        log_adapter_failure(provider="eastmoney", operation="capital_flow", stage="parse", exc=exc)
        return []


@ttl_cache(60, swr=600)
def fetch_announcements(_config: dict, limit: int) -> list[dict]:
    try:
        resp = observed_http_get(
            httpx.get,
            "https://np-anotice-stock.eastmoney.com/api/security/ann",
            provider="eastmoney", operation="announcements",
            host="np-anotice-stock.eastmoney.com", path="/api/security/ann",
            params={"page_index": 1, "page_size": limit, "ann_type": "A",
                    "sort_name": "notice_date", "sort_type": "desc"},
            headers={"User-Agent": "Mozilla/5.0 TodayHighlights/0.1", "Referer": "https://data.eastmoney.com/"},
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
    except Exception as exc:
        log_adapter_failure(provider="eastmoney", operation="announcements", stage="parse", exc=exc)
        return []
