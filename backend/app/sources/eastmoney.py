import re
from datetime import datetime
from hashlib import sha256

import httpx

from app.core.config import SH_TZ, settings
from app.sources.base import RawItemDraft

_proxy = settings.eastmoney_proxy

_PUSH2_HOSTS = ["push2.eastmoney.com", "push2delay.eastmoney.com"]

_headers = {"User-Agent": "Mozilla/5.0 DailyHighlights/0.1", "Referer": "https://quote.eastmoney.com/"}


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
            "gainers": self._fetch_gainers,
            "losers": self._fetch_losers,
            "industry": self._fetch_board,
            "capital_flow": self._fetch_capital_flow,
            "indices": self._fetch_indices,
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

    # ── A-share gainers ──

    def _fetch_gainers(self, subtype: str) -> list[RawItemDraft]:
        resp = _push2_get(
            "/api/qt/clist/get",
            params={"pn": 1, "pz": 20, "po": 1, "np": 1, "fltt": 2, "invt": 2, "fid": "f3",
                    "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
                    "fields": "f2,f3,f4,f12,f14,f20"},
        )
        drafts = []
        for item in resp.json()["data"]["diff"]:
            code = item["f12"]
            name = item["f14"]
            pct = item["f3"]
            price = item["f2"]
            mkt_cap = item.get("f20", 0) or 0
            body = f"{code} 价格 {price:.2f} 市值 {mkt_cap / 1e8:.0f}亿"
            content_str = f"{subtype}|{code}|{pct:.2f}|{price:.2f}"
            drafts.append(RawItemDraft(
                external_id=f"em_{subtype}_{code}",
                url=f"https://quote.eastmoney.com/{code}.html",
                author="",
                title=name,
                body=body,
                published_at=datetime.now(SH_TZ).replace(tzinfo=None),
                metrics={"percent": pct, "current": price, "subtype": subtype, "symbol": code},
                content_hash=sha256(content_str.encode()).hexdigest(),
            ))
        return drafts

    # ── A-share losers ──

    def _fetch_losers(self, subtype: str) -> list[RawItemDraft]:
        resp = _push2_get(
            "/api/qt/clist/get",
            params={"pn": 1, "pz": 20, "po": 0, "np": 1, "fltt": 2, "invt": 2, "fid": "f3",
                    "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
                    "fields": "f2,f3,f4,f12,f14,f20"},
        )
        drafts = []
        for item in resp.json()["data"]["diff"]:
            code = item["f12"]
            name = item["f14"]
            pct = item["f3"]
            price = item["f2"]
            mkt_cap = item.get("f20", 0) or 0
            body = f"{code} 价格 {price:.2f} 市值 {mkt_cap / 1e8:.0f}亿 跌幅 {abs(pct):.2f}%"
            content_str = f"{subtype}|{code}|{pct:.2f}|{price:.2f}"
            drafts.append(RawItemDraft(
                external_id=f"em_{subtype}_{code}",
                url=f"https://quote.eastmoney.com/{code}.html",
                author="",
                title=name,
                body=body,
                published_at=datetime.now(SH_TZ).replace(tzinfo=None),
                metrics={"percent": pct, "current": price, "subtype": subtype, "symbol": code},
                content_hash=sha256(content_str.encode()).hexdigest(),
            ))
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
            headers={"User-Agent": "Mozilla/5.0 DailyHighlights/0.1", "Referer": "https://finance.sina.com.cn/"},
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
