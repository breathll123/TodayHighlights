import re
from datetime import datetime
from hashlib import sha256

import httpx

from app.core.config import SH_TZ, settings
from app.sources.base import RawItemDraft

_proxy = settings.eastmoney_proxy

_PUSH2_HOSTS = ["push2.eastmoney.com", "push2delay.eastmoney.com"]

_headers = {"User-Agent": "Mozilla/5.0 TodayHighlights/0.1", "Referer": "https://quote.eastmoney.com/"}


def _push2_get(path: str, params: dict) -> httpx.Response:
    """Call push2 API with primary + fallback CDN mirror."""
    last_err = None
    for host in _PUSH2_HOSTS:
        try:
            resp = httpx.get(
                f"https://{host}{path}", params=params,
                headers=_headers, timeout=15, follow_redirects=True,
                proxy=_proxy,
            )
            resp.raise_for_status()
            return resp
        except Exception as e:
            last_err = e
    raise last_err  # type: ignore[possibly-unbound]


class EastmoneyAdapter:

    def fetch(self, entry_url: str, cookie: str) -> list[RawItemDraft]:
        subtype = entry_url.replace("eastmoney://", "") if entry_url.startswith("eastmoney://") else ""
        handler = {
            "sectors": self._fetch_board,
            "industry": self._fetch_board,
            "capital_flow": self._fetch_capital_flow,
            "indices": self._fetch_indices,
            "longhu": self._fetch_longhu_datacenter,
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
        resp = _push2_get(
            "/api/qt/clist/get",
            params={"pn": 1, "pz": 50, "po": 1, "np": 1, "fltt": 2, "invt": 2, "fid": "f178",
                    "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
                    "fields": "f2,f3,f8,f12,f14,f152,f174,f175,f176,f177,f178,f179"},
        )
        drafts = []
        for item in resp.json()["data"]["diff"]:
            if item.get("f152") != 2:
                continue
            code = item["f12"]
            name = item["f14"]
            pct = item["f3"]
            buy_amt = (item.get("f174", 0) or 0)
            sell_amt = (item.get("f176", 0) or 0)
            net_amt = buy_amt + sell_amt  # f176 is already negative
            body = f"净买{net_amt/1e8:+.1f}亿 买入{buy_amt/1e8:+.1f}亿 卖出{abs(sell_amt)/1e8:.1f}亿 换手{item.get('f8',0)}%"
            content_str = f"{subtype}|{code}|{buy_amt}|{sell_amt}"
            drafts.append(RawItemDraft(
                external_id=f"em_{subtype}_{code}",
                url=f"https://quote.eastmoney.com/{code}.html",
                author="",
                title=name,
                body=body,
                published_at=datetime.now(SH_TZ).replace(tzinfo=None),
                metrics={
                    "percent": pct, "subtype": subtype, "symbol": code,
                    "buy_amount": buy_amt, "sell_amount": sell_amt,
                    "net_amount": net_amt, "turnover_rate": item.get("f8", 0),
                },
                content_hash=sha256(content_str.encode()).hexdigest(),
            ))
            if len(drafts) >= 20:
                break
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

    # ── indices (via Sina) ──

    def _fetch_indices(self, subtype: str) -> list[RawItemDraft]:
        index_map = [
            ("s_sh000001", "000001"),
            ("s_sz399001", "399001"),
            ("s_sz399006", "399006"),
            ("s_sh000688", "000688"),
            ("s_sz399673", "399673"),
            ("s_sh000300", "000300"),
        ]
        codes = ",".join(c for c, _ in index_map)
        resp = httpx.get(
            f"https://hq.sinajs.cn/list={codes}",
            headers={"User-Agent": "Mozilla/5.0 TodayHighlights/0.1", "Referer": "https://finance.sina.com.cn/"},
            timeout=10,
        )
        resp.raise_for_status()
        text = resp.content.decode("gbk")
        drafts = []
        for symbol, code in index_map:
            m = re.search(rf'hq_str_{symbol}="([^"]*)"', text)
            if not m:
                continue
            fields = m.group(1).split(",")
            if len(fields) < 4:
                continue
            name = fields[0]
            current_val = float(fields[1])
            pct = float(fields[3])
            content_str = f"{subtype}|{code}|{current_val:.2f}|{pct:.2f}"
            drafts.append(RawItemDraft(
                external_id=f"em_{subtype}_{code}",
                url=f"https://quote.eastmoney.com/zs{code}.html",
                author="",
                title=name,
                body=f"{current_val:.2f} {pct:+.2f}%",
                published_at=datetime.now(SH_TZ).replace(tzinfo=None),
                metrics={"percent": pct, "current": current_val, "subtype": subtype, "symbol": code},
                content_hash=sha256(content_str.encode()).hexdigest(),
            ))
        return drafts

    # ── longhu (via datacenter-web API) ──

    _lhb_cookie: str | None = None
    _lhb_cookie_ts: float = 0

    @classmethod
    def _get_lhb_cookie(cls) -> str:
        """Get datacenter-web cookie via Playwright (auto-refreshed every 30min)."""
        import time as _time
        now = _time.time()
        if cls._lhb_cookie and (now - cls._lhb_cookie_ts) < 1800:
            return cls._lhb_cookie
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context()
            page = ctx.new_page()
            page.goto("https://data.eastmoney.com/stock/lhb.html", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)
            cookies = {c["name"]: c["value"] for c in ctx.cookies()}
            browser.close()
        cls._lhb_cookie = "; ".join(f"{k}={v}" for k, v in cookies.items())
        cls._lhb_cookie_ts = now
        return cls._lhb_cookie

    def _fetch_longhu_datacenter(self, subtype: str) -> list[RawItemDraft]:
        cookie = self._get_lhb_cookie()
        resp = httpx.get(
            "https://datacenter-web.eastmoney.com/api/data/v1/get",
            params={"reportName": "RPT_ORGANIZATION_TRADE_DETAILSNEW", "columns": "ALL",
                    "pageNumber": 1, "pageSize": 100, "sortTypes": "-1", "sortColumns": "TRADE_DATE",
                    "source": "WEB", "client": "WEB"},
            headers={"Cookie": cookie, "User-Agent": "Mozilla/5.0", "Referer": "https://data.eastmoney.com/stock/lhb.html"},
            timeout=15,
        )
        resp.raise_for_status()
        items = resp.json().get("result", {}).get("data", []) or []
        # Filter latest trading day, sort by NET_BUY_AMT desc
        if items:
            latest_date = str(items[0].get("TRADE_DATE", ""))[:10]
            today_items = [i for i in items if str(i.get("TRADE_DATE", ""))[:10] == latest_date]
            today_items.sort(key=lambda x: abs(x.get("NET_BUY_AMT", 0) or 0), reverse=True)
        else:
            today_items = []
        drafts = []
        for item in today_items:
            code = item.get("SECURITY_CODE", "")
            name = item.get("SECURITY_NAME_ABBR", "")
            pct_val = item.get("CHANGE_RATE", 0) or 0
            net_buy = (item.get("NET_BUY_AMT", 0) or 0)
            buy_amt = (item.get("BUY_AMT", 0) or 0)
            sell_amt = (item.get("SELL_AMT", 0) or 0)
            reason = item.get("EXPLANATION", "")
            body = f"净买{net_buy/1e8:+.1f}亿 买{buy_amt/1e8:.1f}亿 卖{abs(sell_amt)/1e8:.1f}亿  {reason}"
            content_str = f"{subtype}|{code}|{net_buy}|{buy_amt}"
            drafts.append(RawItemDraft(
                external_id=f"lhb_{code}_{item.get('TRADE_DATE','')}",
                url=f"https://quote.eastmoney.com/{code}.html",
                author="",
                title=name,
                body=body,
                published_at=datetime.now(SH_TZ).replace(tzinfo=None),
                metrics={"percent": float(pct_val), "subtype": subtype, "symbol": code,
                         "net_buy": net_buy, "buy_amt": buy_amt, "sell_amt": sell_amt, "reason": reason},
                content_hash=sha256(content_str.encode()).hexdigest(),
            ))
            if len(drafts) >= 20:
                break
        return drafts

