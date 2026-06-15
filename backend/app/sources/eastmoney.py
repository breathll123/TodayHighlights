import json
from datetime import datetime
from hashlib import sha256

import httpx

from app.core.config import SH_TZ, settings
from app.core.logging import observed_http_get
from app.sources.base import RawItemDraft

_proxy = settings.eastmoney_proxy

_PUSH2_HOSTS = ["push2.eastmoney.com", "push2delay.eastmoney.com"]

_headers = {"User-Agent": "Mozilla/5.0 TodayHighlights/0.1", "Referer": "https://quote.eastmoney.com/"}


def _push2_get(path: str, params: dict) -> httpx.Response:
    """Call push2 API with primary + fallback CDN mirror."""
    last_err = None
    for host in _PUSH2_HOSTS:
        try:
            resp = observed_http_get(
                httpx.get,
                f"https://{host}{path}", params=params,
                provider="eastmoney",
                operation="push2",
                host=host,
                path=path,
                headers=_headers, timeout=15, follow_redirects=True,
                proxy=_proxy,
            )
            resp.raise_for_status()
            return resp
        except Exception as e:
            last_err = e
    raise last_err  # type: ignore[possibly-unbound]


def _datacenter_longhu_get() -> httpx.Response:
    response = observed_http_get(
        httpx.get,
        "https://datacenter-web.eastmoney.com/api/data/v1/get",
        provider="eastmoney",
        operation="longhu_detail",
        host="datacenter-web.eastmoney.com",
        path="/api/data/v1/get",
        params={
            "reportName": "RPT_DAILYBILLBOARD_DETAILSNEW",
            "columns": "ALL",
            "pageNumber": 1,
            "pageSize": 500,
            "sortTypes": "-1",
            "sortColumns": "TRADE_DATE",
            "source": "WEB",
            "client": "WEB",
        },
        headers={
            "User-Agent": "Mozilla/5.0 TodayHighlights/0.1",
            "Referer": "https://data.eastmoney.com/stock/tradedetail.html",
            "Accept": "application/json,text/plain,*/*",
        },
        timeout=20,
        follow_redirects=True,
        proxy=_proxy,
    )
    response.raise_for_status()
    return response


class EastmoneyAdapter:

    def fetch(self, entry_url: str, cookie: str) -> list[RawItemDraft]:
        subtype = entry_url.replace("eastmoney://", "") if entry_url.startswith("eastmoney://") else ""
        handler = {
            "sectors": self._fetch_board,
            "industry": self._fetch_board,
            "capital_flow": self._fetch_capital_flow,
            "indices": self._fetch_indices,
            "longhu": self._fetch_longhu,
        }.get(subtype)
        if handler is None:
            return []
        return handler(subtype)

    # ── board data (sectors / industry) ──

    def _fetch_board(self, subtype: str) -> list[RawItemDraft]:
        fs_map = {"sectors": "m:90+t:3", "industry": "m:90+t:2"}
        fs = fs_map.get(subtype, "m:90+t:3")
        resp = _push2_get(
            "/api/qt/clist/get",
            params={"pn": 1, "pz": 20, "po": 1, "np": 1, "fltt": 2, "invt": 2, "fid": "f3", "fs": fs,
                    "fields": "f2,f3,f4,f12,f14"},
        )
        drafts = []
        for item in resp.json()["data"]["diff"]:
            code = item["f12"]
            name = item["f14"]
            pct = item["f3"]
            current_val = item["f2"]
            body = f"指数 {current_val:.2f} 涨跌幅 {pct:+.2f}%"
            content_str = f"{subtype}|{code}|{pct:.2f}|{current_val:.2f}"
            drafts.append(RawItemDraft(
                external_id=f"em_{subtype}_{code}",
                url=f"https://quote.eastmoney.com/bk/90.{code}.html",
                author="",
                title=name,
                body=body,
                published_at=datetime.now(SH_TZ).replace(tzinfo=None),
                metrics={"percent": pct, "current": current_val, "subtype": subtype, "symbol": code},
                content_hash=sha256(content_str.encode()).hexdigest(),
            ))
        return drafts

    # ── 龙虎榜 ──

    def _fetch_longhu(self, subtype: str) -> list[RawItemDraft]:
        return self._fetch_longhu_datacenter(subtype)

    def _fetch_longhu_datacenter(self, subtype: str) -> list[RawItemDraft]:
        response = _datacenter_longhu_get()
        payload = response.json()
        if not payload.get("success"):
            raise RuntimeError(payload.get("message") or "Eastmoney longhu response was unsuccessful")

        items = payload.get("result", {}).get("data", []) or []
        if not items:
            return []

        latest_date = max(str(item.get("TRADE_DATE") or "")[:10] for item in items)
        latest_items = [
            item for item in items
            if str(item.get("TRADE_DATE") or "")[:10] == latest_date
        ]
        latest_items.sort(
            key=lambda item: abs(float(item.get("BILLBOARD_NET_AMT") or 0)),
            reverse=True,
        )

        drafts: list[RawItemDraft] = []
        for item in latest_items[:100]:
            code = str(item.get("SECURITY_CODE") or "")
            name = str(item.get("SECURITY_NAME_ABBR") or "")
            trade_id = str(item.get("TRADE_ID") or "")
            reason = str(item.get("EXPLANATION") or "")
            if not code or not name:
                continue

            buy_amount = float(item.get("BILLBOARD_BUY_AMT") or 0)
            sell_amount = float(item.get("BILLBOARD_SELL_AMT") or 0)
            net_amount = float(item.get("BILLBOARD_NET_AMT") or 0)
            turnover_rate = float(item.get("TURNOVERRATE") or 0)
            raw_snapshot = json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
            identity = trade_id or sha256(f"{code}|{reason}".encode()).hexdigest()[:16]
            content_hash = sha256(raw_snapshot.encode()).hexdigest()

            drafts.append(
                RawItemDraft(
                    external_id=f"lhb_{latest_date}_{identity}",
                    url=f"https://quote.eastmoney.com/{code}.html",
                    author="",
                    title=name,
                    body=(
                        f"净买{net_amount / 1e8:+.1f}亿 "
                        f"买入{buy_amount / 1e8:.1f}亿 "
                        f"卖出{sell_amount / 1e8:.1f}亿 "
                        f"换手{turnover_rate:.2f}% {reason}"
                    ),
                    published_at=datetime.fromisoformat(f"{latest_date}T00:00:00"),
                    metrics={
                        "percent": float(item.get("CHANGE_RATE") or 0),
                        "current": float(item.get("CLOSE_PRICE") or 0),
                        "subtype": subtype,
                        "symbol": code,
                        "secucode": str(item.get("SECUCODE") or ""),
                        "trade_date": latest_date,
                        "trade_id": item.get("TRADE_ID"),
                        "buy_amount": buy_amount,
                        "sell_amount": sell_amount,
                        "net_amount": net_amount,
                        "net_buy": net_amount,
                        "billboard_deal_amount": float(item.get("BILLBOARD_DEAL_AMT") or 0),
                        "deal_amount_ratio": float(item.get("DEAL_AMOUNT_RATIO") or 0),
                        "deal_net_ratio": float(item.get("DEAL_NET_RATIO") or 0),
                        "turnover_rate": turnover_rate,
                        "free_market_cap": float(item.get("FREE_MARKET_CAP") or 0),
                        "reason": reason,
                        "institution_summary": str(item.get("EXPLAIN") or ""),
                        "post_change_1d": item.get("D1_CLOSE_ADJCHRATE"),
                        "post_change_2d": item.get("D2_CLOSE_ADJCHRATE"),
                        "post_change_5d": item.get("D5_CLOSE_ADJCHRATE"),
                        "post_change_10d": item.get("D10_CLOSE_ADJCHRATE"),
                    },
                    content_hash=content_hash,
                    raw_snapshot=raw_snapshot,
                )
            )
        return drafts

    # ── capital flow ──

    def _fetch_capital_flow(self, subtype: str) -> list[RawItemDraft]:
        resp = _push2_get(
            "/api/qt/clist/get",
            params={"pn": 1, "pz": 20, "po": 1, "np": 1, "fltt": 2, "invt": 2, "fid": "f62",
                    "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
                    "fields": "f2,f3,f12,f14,f62,f64,f66"},
        )
        drafts = []
        for item in resp.json()["data"]["diff"]:
            code = item["f12"]
            name = item["f14"]
            pct = item["f3"]
            inflow = (item.get("f62", 0) or 0)
            content_str = f"{subtype}|{code}|{inflow}"
            drafts.append(RawItemDraft(
                external_id=f"em_{subtype}_{code}",
                url=f"https://quote.eastmoney.com/{code}.html",
                author="",
                title=name,
                body=f"{code} 主力净流入{inflow / 1e8:.1f}亿",
                published_at=datetime.now(SH_TZ).replace(tzinfo=None),
                metrics={"percent": pct, "subtype": subtype, "symbol": code, "inflow": inflow},
                content_hash=sha256(content_str.encode()).hexdigest(),
            ))
        return drafts

    # ── indices ──

    def _fetch_indices(self, subtype: str) -> list[RawItemDraft]:
        index_map = [
            ("000001", "1.000001"),
            ("399001", "0.399001"),
            ("399006", "0.399006"),
            ("000688", "1.000688"),
            ("399673", "0.399673"),
            ("000300", "1.000300"),
        ]
        resp = _push2_get(
            "/api/qt/ulist.np/get",
            params={
                "fltt": 2,
                "invt": 2,
                "fields": "f2,f3,f4,f5,f6,f12,f13,f14",
                "secids": ",".join(secid for _, secid in index_map),
            },
        )
        items = resp.json().get("data", {}).get("diff", [])
        known_codes = {code for code, _ in index_map}
        drafts = []
        for item in items:
            code = str(item.get("f12") or "")
            if code not in known_codes:
                continue
            name = str(item.get("f14") or "")
            current_val = float(item.get("f2") or 0)
            pct = float(item.get("f3") or 0)
            change_amount = float(item.get("f4") or 0)
            volume = int(item.get("f5") or 0)
            turnover = float(item.get("f6") or 0)
            content_str = f"{subtype}|{code}|{current_val:.2f}|{pct:.2f}"
            drafts.append(RawItemDraft(
                external_id=f"em_{subtype}_{code}",
                url=f"https://quote.eastmoney.com/zs{code}.html",
                author="",
                title=name,
                body=f"{current_val:.2f} {pct:+.2f}%",
                published_at=datetime.now(SH_TZ).replace(tzinfo=None),
                metrics={
                    "percent": pct,
                    "current": current_val,
                    "change_amount": change_amount,
                    "volume": volume,
                    "turnover": turnover,
                    "subtype": subtype,
                    "symbol": code,
                },
                content_hash=sha256(content_str.encode()).hexdigest(),
            ))
        return drafts
