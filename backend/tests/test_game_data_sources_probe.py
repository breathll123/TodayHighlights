"""Manual connectivity probe for mainland-friendly game data candidates.

Run directly from backend:
    python tests/test_game_data_sources_probe.py --plan-only
    python tests/test_game_data_sources_probe.py
    python tests/test_game_data_sources_probe.py --only taptap_top
    python tests/test_game_data_sources_probe.py --output /tmp/game_sources_probe.json

This file is intentionally a manual probe. The pytest tests only validate the
request plan and do not hit third-party sites.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

import httpx


Headers = dict[str, str]
Params = dict[str, Any]
STEAM_REGION = "CN"
STEAM_LANGUAGE = "schinese"


@dataclass(frozen=True)
class ProbeRequest:
    key: str
    title: str
    purpose: str
    method: str
    url: str
    params: Params | None = None
    headers: Headers | None = None


class HtmlSignalParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.meta_description = ""
        self.preload_image_count = 0
        self.image_urls: list[str] = []
        self.links: list[str] = []
        self.script_sources: list[str] = []
        self.text_chunks: list[str] = []
        self._tag_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._tag_stack.append(tag)
        attr_map = {key.lower(): value or "" for key, value in attrs}
        if tag == "meta":
            name = (attr_map.get("name") or attr_map.get("property") or "").lower()
            if name in {"description", "og:description"} and not self.meta_description:
                self.meta_description = attr_map.get("content", "")[:300]
        elif tag == "link":
            href = attr_map.get("href")
            rel = attr_map.get("rel", "")
            as_value = attr_map.get("as", "")
            if href:
                self.links.append(href)
            if "preload" in rel and as_value == "image":
                self.preload_image_count += 1
        elif tag == "img":
            src = attr_map.get("src") or attr_map.get("data-src")
            if src:
                self.image_urls.append(src)
        elif tag == "script":
            src = attr_map.get("src")
            if src:
                self.script_sources.append(src)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self._tag_stack) - 1, -1, -1):
            if self._tag_stack[index] == tag:
                del self._tag_stack[index:]
                return

    def handle_data(self, data: str) -> None:
        text = re.sub(r"\s+", " ", data).strip()
        if not text:
            return
        current_tag = self._tag_stack[-1] if self._tag_stack else ""
        if current_tag == "title" and not self.title:
            self.title = text[:200]
            return
        if current_tag in {"script", "style", "noscript"}:
            return
        if len(text) >= 4 and re.search(r"[\u4e00-\u9fffA-Za-z0-9]", text):
            self.text_chunks.append(text[:160])


def browser_headers(referer: str) -> Headers:
    return {
        "User-Agent": "Mozilla/5.0 TodayHighlights/0.1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": referer,
    }


def steam_api_headers(referer: str) -> Headers:
    return {
        "User-Agent": "Mozilla/5.0 TodayHighlights/0.1",
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": referer,
    }


def build_steam_appdetails_probe_url(appid: str) -> str:
    safe_appid = quote(str(appid), safe="")
    return (
        "https://store.steampowered.com/api/appdetails"
        f"?appids={safe_appid}&cc={STEAM_REGION}&l={STEAM_LANGUAGE}&filters=basic"
    )


def build_probe_plan() -> list[ProbeRequest]:
    return [
        ProbeRequest(
            key="steam_charts_mostplayed_page",
            title="Steam Charts 在线热玩页面",
            purpose="页面探测。用于确认 Steam Charts 页面是否服务端直出榜单，或是否需要进一步定位页面调用的接口。",
            method="GET",
            url="https://store.steampowered.com/charts/mostplayed",
            params={"cc": "CN", "l": "schinese"},
            headers=browser_headers("https://store.steampowered.com/"),
        ),
        ProbeRequest(
            key="steam_charts_concurrent_api",
            title="Steam Charts 当前在线人数接口",
            purpose="实时热玩榜候选。返回 rank、appid、concurrent_in_game、peak_in_game，可复现页面按当前玩家数排序的数据。",
            method="GET",
            url="https://api.steampowered.com/ISteamChartsService/GetGamesByConcurrentPlayers/v1/",
            params={"format": "json"},
            headers=steam_api_headers("https://store.steampowered.com/charts/mostplayed"),
        ),
        ProbeRequest(
            key="taptap_top",
            title="TapTap 热门榜",
            purpose="热门游戏榜候选。优先看榜单页是否稳定返回，后续可解析游戏名、评分、标签、封面。",
            method="GET",
            url="https://www.taptap.cn/top/download",
            headers=browser_headers("https://www.taptap.cn/"),
        ),
        ProbeRequest(
            key="taptap_new",
            title="TapTap 新游/预约",
            purpose="新游动态候选。适合覆盖手游、国产游戏、测试招募和预约热度。",
            method="GET",
            url="https://www.taptap.cn/top/reserve",
            headers=browser_headers("https://www.taptap.cn/"),
        ),
        ProbeRequest(
            key="wegame_store",
            title="WeGame 商店",
            purpose="PC 游戏与国内发行游戏候选。可用于验证商店页、活动页、折扣页是否可访问。",
            method="GET",
            url="https://www.wegame.com.cn/store/games",
            headers=browser_headers("https://www.wegame.com.cn/"),
        ),
        ProbeRequest(
            key="sonkwo_store",
            title="杉果游戏商店",
            purpose="打折促销候选。杉果是国内 PC 游戏商店，适合验证折扣、价格、封面和商店链接。",
            method="GET",
            url="https://www.sonkwo.cn/",
            headers=browser_headers("https://www.sonkwo.cn/"),
        ),
        ProbeRequest(
            key="gamersky_news",
            title="游民星空游戏资讯",
            purpose="新游动态与行业快讯候选。适合解析标题、发布时间、摘要、封面。",
            method="GET",
            url="https://www.gamersky.com/news/",
            headers=browser_headers("https://www.gamersky.com/"),
        ),
        ProbeRequest(
            key="gamersky_ku",
            title="游民星空游戏库",
            purpose="新游资料候选。适合补充游戏基础信息、发售日期、平台等资料。",
            method="GET",
            url="https://ku.gamersky.com/",
            headers=browser_headers("https://ku.gamersky.com/"),
        ),
        ProbeRequest(
            key="ali213_new",
            title="游侠网新游资讯",
            purpose="新游动态候选。可作为游民星空的备选来源，验证国内站点访问速度。",
            method="GET",
            url="https://www.ali213.net/news/",
            headers=browser_headers("https://www.ali213.net/"),
        ),
        ProbeRequest(
            key="3dm_game_news",
            title="3DM 游戏新闻",
            purpose="游戏新闻与行业快讯候选。这个分类页比 3DM 新闻首页更聚焦游戏内容，可与游民星空、游侠互为备份。",
            method="GET",
            url="https://www.3dmgame.com/news/game/",
            headers=browser_headers("https://www.3dmgame.com/"),
        ),
    ]


def printable_url(request: ProbeRequest) -> str:
    if not request.params:
        return request.url
    return f"{request.url}?{urlencode(request.params)}"


def summarize_steam_charts(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    response = payload.get("response")
    if not isinstance(response, dict):
        return None
    ranks = response.get("ranks")
    if not isinstance(ranks, list):
        return None

    sample_ranks = [row for row in ranks[:5] if isinstance(row, dict)]
    return {
        "rank_count": len(ranks),
        "last_update": response.get("last_update"),
        "rollup_date": response.get("rollup_date"),
        "first_rank_keys": sorted(str(key) for key in sample_ranks[0].keys()) if sample_ranks else [],
        "has_current_players": any("concurrent_in_game" in row for row in sample_ranks),
        "has_peak_players": any("peak_in_game" in row for row in sample_ranks),
        "sample_ranks": sample_ranks,
    }


def extract_steam_chart_rows(payload: Any, limit: int) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    response = payload.get("response")
    if not isinstance(response, dict):
        return []
    ranks = response.get("ranks")
    if not isinstance(ranks, list):
        return []
    return [row for row in ranks[:limit] if isinstance(row, dict) and row.get("appid") is not None]


def hydrate_steam_chart_games(payload: Any, *, timeout: float, limit: int) -> list[dict[str, Any]]:
    rows = extract_steam_chart_rows(payload, limit)
    if not rows:
        return []

    games: list[dict[str, Any]] = []
    headers = steam_api_headers("https://store.steampowered.com/charts/mostplayed")
    with httpx.Client(follow_redirects=True, timeout=timeout) as client:
        for row in rows:
            appid = str(row.get("appid"))
            detail_summary: dict[str, Any] = {
                "rank": row.get("rank"),
                "appid": appid,
                "source_url": f"https://store.steampowered.com/app/{quote(appid, safe='')}/",
                "concurrent_in_game": row.get("concurrent_in_game"),
                "peak_in_game": row.get("peak_in_game"),
                "last_week_rank": row.get("last_week_rank"),
            }
            try:
                response = client.get(build_steam_appdetails_probe_url(appid), headers=headers)
                detail_summary["detail_status_code"] = response.status_code
                response.raise_for_status()
                payload = response.json()
                app_payload = payload.get(appid) if isinstance(payload, dict) else None
                data = app_payload.get("data") if isinstance(app_payload, dict) and app_payload.get("success") else None
                if isinstance(data, dict):
                    detail_summary.update(
                        {
                            "name": data.get("name"),
                            "type": data.get("type"),
                            "header_image": data.get("header_image"),
                            "capsule_image": data.get("capsule_image"),
                            "short_description": data.get("short_description"),
                        }
                    )
                else:
                    detail_summary["detail_error"] = "appdetails response missing data"
            except Exception as exc:
                detail_summary["detail_error"] = f"{type(exc).__name__}: {exc}"
            games.append(detail_summary)
    return games


def summarize_json(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        summary: dict[str, Any] = {
            "json_type": "object",
            "top_level_keys": sorted(str(k) for k in payload.keys())[:30],
        }
        steam_charts = summarize_steam_charts(payload)
        if steam_charts is not None:
            summary["steam_charts"] = steam_charts
        return summary
    if isinstance(payload, list):
        summary: dict[str, Any] = {"json_type": "array", "item_count": len(payload)}
        if payload and isinstance(payload[0], dict):
            summary["first_item_keys"] = sorted(payload[0].keys())
        return summary
    return {"json_type": type(payload).__name__}


def find_data_markers(text: str) -> list[str]:
    markers = [
        "__NEXT_DATA__",
        "__NUXT__",
        "__INITIAL_STATE__",
        "__APOLLO_STATE__",
        "window.__INITIAL_STATE__",
        "application/json",
        "ld+json",
        "data-release",
        "antidom",
    ]
    return [marker for marker in markers if marker in text]


def summarize_html(text: str) -> dict[str, Any]:
    parser = HtmlSignalParser()
    parser.feed(text[:2_000_000])
    data_markers = find_data_markers(text)
    risk_flags = []
    if "antidom" in data_markers:
        risk_flags.append("contains_antidom_script")
    if parser.script_sources and not parser.text_chunks:
        risk_flags.append("likely_client_rendered")

    text_samples = []
    seen = set()
    for chunk in parser.text_chunks:
        normalized = chunk.strip()
        if normalized and normalized not in seen:
            text_samples.append(normalized)
            seen.add(normalized)
        if len(text_samples) >= 20:
            break

    return {
        "title": parser.title,
        "meta_description": parser.meta_description,
        "data_markers": data_markers,
        "risk_flags": risk_flags,
        "script_count": len(parser.script_sources),
        "script_src_sample": parser.script_sources[:10],
        "preload_image_count": parser.preload_image_count,
        "img_count": len(parser.image_urls),
        "img_src_sample": parser.image_urls[:10],
        "link_count": len(parser.links),
        "link_href_sample": parser.links[:10],
        "text_sample_count": len(text_samples),
        "text_samples": text_samples,
        "parse_hint": "server_text_or_data_found" if text_samples or data_markers else "needs_browser_or_api_capture",
    }


def summarize_response(response: httpx.Response) -> dict[str, Any]:
    content_type = response.headers.get("content-type", "")
    summary: dict[str, Any] = {
        "status_code": response.status_code,
        "content_type": content_type,
        "bytes": len(response.content),
        "final_url": str(response.url),
    }
    text = response.text.strip()
    if "application/json" in content_type or text.startswith(("{", "[")):
        try:
            summary["json"] = summarize_json(response.json())
            return summary
        except ValueError:
            summary["json_error"] = "response is not valid json"

    summary["text_preview"] = text[:500].replace("\n", " ")
    summary["contains_html"] = "<html" in text.lower() or "<!doctype html" in text.lower()
    if summary["contains_html"]:
        summary["html"] = summarize_html(text)
    return summary


def build_safe_html_preview(request_key: str, response: httpx.Response) -> str:
    text = response.text
    summary = summarize_html(text) if "<html" in text.lower() or "<!doctype html" in text.lower() else {}
    text_samples = summary.get("text_samples") or []
    images = summary.get("img_src_sample") or []
    links = summary.get("link_href_sample") or []
    markers = summary.get("data_markers") or []
    risks = summary.get("risk_flags") or []
    title = summary.get("title") or request_key

    def list_items(values: list[Any]) -> str:
        if not values:
            return "<li>无</li>"
        return "".join(f"<li>{escape(str(value))}</li>" for value in values)

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(str(title))} - safe preview</title>
  <style>
    body {{ margin: 0; padding: 24px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #0f172a; color: #e5e7eb; }}
    main {{ max-width: 1040px; margin: 0 auto; }}
    section {{ border: 1px solid #334155; background: #111827; border-radius: 12px; padding: 18px; margin: 14px 0; }}
    h1 {{ margin: 0 0 8px; font-size: 24px; }}
    h2 {{ margin: 0 0 12px; font-size: 16px; color: #93c5fd; }}
    code, pre {{ background: #020617; border: 1px solid #1f2937; border-radius: 8px; }}
    code {{ padding: 2px 6px; }}
    pre {{ padding: 12px; white-space: pre-wrap; overflow-wrap: anywhere; color: #cbd5e1; }}
    li {{ margin: 6px 0; line-height: 1.5; }}
    .muted {{ color: #94a3b8; }}
  </style>
</head>
<body>
<main>
  <h1>{escape(str(title))}</h1>
  <p class="muted">安全预览：已禁用原页面脚本，避免 file:// 环境跳转。原始 HTML 请看同目录 raw 文件。</p>
  <section>
    <h2>解析判断</h2>
    <ul>
      <li>data markers: <code>{escape(", ".join(str(x) for x in markers) or "无")}</code></li>
      <li>risk flags: <code>{escape(", ".join(str(x) for x in risks) or "无")}</code></li>
      <li>parse hint: <code>{escape(str(summary.get("parse_hint", "unknown")))}</code></li>
      <li>script count: <code>{escape(str(summary.get("script_count", 0)))}</code></li>
      <li>image count: <code>{escape(str(summary.get("img_count", 0)))}</code></li>
    </ul>
  </section>
  <section>
    <h2>页面文本样本</h2>
    <ul>{list_items(text_samples)}</ul>
  </section>
  <section>
    <h2>图片样本</h2>
    <ul>{list_items(images)}</ul>
  </section>
  <section>
    <h2>链接样本</h2>
    <ul>{list_items(links)}</ul>
  </section>
  <section>
    <h2>原始 HTML 前 6000 字符</h2>
    <pre>{escape(text[:6000])}</pre>
  </section>
</main>
</body>
</html>
"""


def save_body(request_key: str, response: httpx.Response, save_body_dir: Path | None) -> dict[str, str] | None:
    if save_body_dir is None:
        return None
    save_body_dir.mkdir(parents=True, exist_ok=True)
    suffix = ".json" if "json" in response.headers.get("content-type", "") else ".html"
    raw_path = save_body_dir / f"{request_key}.raw{suffix}"
    raw_path.write_bytes(response.content)
    paths = {"raw": str(raw_path.resolve())}
    if suffix == ".html":
        preview_path = save_body_dir / f"{request_key}.preview.html"
        preview_path.write_text(build_safe_html_preview(request_key, response), encoding="utf-8")
        paths["preview"] = str(preview_path.resolve())
    return paths


def run_probe(
    request: ProbeRequest,
    *,
    timeout: float,
    save_body_dir: Path | None = None,
    hydrate_steam_details: bool = False,
    steam_detail_limit: int = 5,
) -> dict[str, Any]:
    base_result = {
        "key": request.key,
        "title": request.title,
        "purpose": request.purpose,
        "method": request.method,
        "url": printable_url(request),
    }
    started = time.perf_counter()
    try:
        with httpx.Client(follow_redirects=True) as client:
            response = client.request(
                request.method,
                request.url,
                params=request.params,
                headers=request.headers,
                timeout=timeout,
            )
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response_summary = summarize_response(response)
        if hydrate_steam_details and request.key == "steam_charts_concurrent_api":
            try:
                payload = response.json()
                response_summary.setdefault("json", {})["steam_chart_games"] = hydrate_steam_chart_games(
                    payload,
                    timeout=timeout,
                    limit=steam_detail_limit,
                )
            except ValueError:
                response_summary.setdefault("json", {})["steam_chart_games_error"] = "response is not valid json"
        return {
            **base_result,
            "status": "ok" if response.is_success else "http_error",
            "duration_ms": duration_ms,
            "response": response_summary,
            "saved_body": save_body(request.key, response, save_body_dir),
        }
    except Exception as exc:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        return {
            **base_result,
            "status": "failed",
            "duration_ms": duration_ms,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def print_source_plan(plan: list[ProbeRequest]) -> None:
    print("候选数据源和请求:")
    for request in plan:
        print(f"\n[{request.key}] {request.title}")
        print(f"  用途: {request.purpose}")
        print(f"  请求: {request.method} {printable_url(request)}")
        print("  认证: 不需要 key")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="探测游戏主题国内候选数据源能否访问")
    parser.add_argument("--only", choices=[p.key for p in build_probe_plan()], help="只探测某一个数据源")
    parser.add_argument("--timeout", type=float, default=20, help="请求超时秒数，默认 20")
    parser.add_argument("--output", type=Path, help="可选：保存完整探测结果 JSON")
    parser.add_argument("--save-body-dir", type=Path, help="可选：保存 raw 原文和禁脚本 preview，便于后续写解析器")
    parser.add_argument("--hydrate-steam-details", action="store_true", help="对 Steam Charts 榜单额外请求 appdetails，补游戏名、封面和简介")
    parser.add_argument("--steam-detail-limit", type=int, default=5, help="补齐 Steam 游戏详情的条数，默认 5")
    parser.add_argument("--plan-only", action="store_true", help="只打印请求计划，不实际联网")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    plan = build_probe_plan()
    if args.only:
        plan = [p for p in plan if p.key == args.only]

    print_source_plan(plan)
    if args.plan_only:
        return

    print("\n探测结果:")
    results = []
    for request in plan:
        result = run_probe(
            request,
            timeout=args.timeout,
            save_body_dir=args.save_body_dir,
            hydrate_steam_details=args.hydrate_steam_details,
            steam_detail_limit=args.steam_detail_limit,
        )
        results.append(result)
        print(f"\n[{result['key']}] {result['title']}")
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(f"\n完整结果已保存到: {args.output.resolve()}")


def test_build_probe_plan_contains_mainland_friendly_sources() -> None:
    keys = [request.key for request in build_probe_plan()]

    assert keys == [
        "steam_charts_mostplayed_page",
        "steam_charts_concurrent_api",
        "taptap_top",
        "taptap_new",
        "wegame_store",
        "sonkwo_store",
        "gamersky_news",
        "gamersky_ku",
        "ali213_new",
        "3dm_game_news",
    ]


def test_probe_requests_do_not_require_api_keys() -> None:
    for request in build_probe_plan():
        assert request.method == "GET"
        assert request.headers is not None
        assert "User-Agent" in request.headers


def test_first_batch_covers_rank_deals_and_new_releases() -> None:
    plan = build_probe_plan()
    text = " ".join(f"{request.title} {request.purpose}" for request in plan)

    assert "热门" in text
    assert "打折" in text
    assert "新游" in text


def test_summarize_json_reports_steam_charts_fields() -> None:
    payload = {
        "response": {
            "last_update": 1783092924,
            "ranks": [
                {"rank": 1, "appid": 730, "concurrent_in_game": 1260857, "peak_in_game": 1336231},
                {"rank": 2, "appid": 570, "concurrent_in_game": 767491, "peak_in_game": 767491},
            ],
        }
    }

    summary = summarize_json(payload)

    assert summary["steam_charts"]["rank_count"] == 2
    assert summary["steam_charts"]["has_current_players"] is True
    assert summary["steam_charts"]["has_peak_players"] is True
    assert summary["steam_charts"]["first_rank_keys"] == [
        "appid",
        "concurrent_in_game",
        "peak_in_game",
        "rank",
    ]
    assert summary["steam_charts"]["sample_ranks"][0]["appid"] == 730


def test_extract_steam_chart_rows_filters_invalid_rows() -> None:
    payload = {
        "response": {
            "ranks": [
                {"rank": 1, "appid": 730, "peak_in_game": 100},
                {"rank": 2, "peak_in_game": 50},
                "bad",
                {"rank": 3, "appid": 570, "peak_in_game": 80},
            ]
        }
    }

    rows = extract_steam_chart_rows(payload, 10)

    assert [row["appid"] for row in rows] == [730, 570]


def test_build_steam_appdetails_probe_url() -> None:
    url = build_steam_appdetails_probe_url("730")

    assert "store.steampowered.com/api/appdetails" in url
    assert "appids=730" in url
    assert "cc=CN" in url
    assert "l=schinese" in url
    assert "filters=basic" in url


def test_summarize_html_reports_parse_signals() -> None:
    html = """
    <!doctype html>
    <html data-release="2026-6-26">
      <head>
        <title>热门榜 - TapTap</title>
        <meta name="description" content="热门游戏榜">
        <script src="//example.com/antidom.js"></script>
        <script id="__NEXT_DATA__" type="application/json">{"props": {}}</script>
        <link rel="preload" as="image" href="https://img.example.com/a.png">
      </head>
      <body>
        <a href="/app/1">测试游戏一</a>
        <span>9.1 分</span>
      </body>
    </html>
    """

    summary = summarize_html(html)

    assert summary["title"] == "热门榜 - TapTap"
    assert summary["meta_description"] == "热门游戏榜"
    assert "__NEXT_DATA__" in summary["data_markers"]
    assert "antidom" in summary["data_markers"]
    assert "contains_antidom_script" in summary["risk_flags"]
    assert summary["preload_image_count"] == 1
    assert summary["parse_hint"] == "server_text_or_data_found"
    assert "测试游戏一" in summary["text_samples"]


def test_save_body_writes_html_response(tmp_path) -> None:
    response = httpx.Response(
        200,
        headers={"content-type": "text/html;charset=utf-8"},
        content=b"<html><title>x</title></html>",
    )

    saved = save_body("sample", response, tmp_path)

    assert saved is not None
    raw_path = Path(saved["raw"])
    preview_path = Path(saved["preview"])
    assert raw_path.name == "sample.raw.html"
    assert preview_path.name == "sample.preview.html"
    assert raw_path.read_text(encoding="utf-8") == "<html><title>x</title></html>"
    assert "安全预览" in preview_path.read_text(encoding="utf-8")


if __name__ == "__main__":
    main()
