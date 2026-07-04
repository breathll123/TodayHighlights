# -*- coding: utf-8 -*-
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import settings
from app.core.logging import log_adapter_failure, observed_http_get


def build_steam_url(endpoint_key: str) -> str:
    """
    根据给定的接口类型，构建对应的 Steam 搜索接口 URL。
    """
    base = "https://store.steampowered.com/search/results/"
    # 基础参数：无限滚动，开启中国区，开启简体中文
    params = f"?query=&start=0&count=50&dynamic_data=&sort_by=_ASC&infinite=1&cc={settings.steam_region}&l={settings.steam_language}"
    
    if endpoint_key == "top_sellers":
        return f"{base}{params}&filter=topsellers"
    elif endpoint_key == "specials":
        return f"{base}{params}&specials=1"
    elif endpoint_key == "new_releases":
        return (
            f"{base}?query=&start=0&count=50&dynamic_data=&sort_by=Released_DESC"
            f"&infinite=1&cc={settings.steam_region}&l={settings.steam_language}"
        )
    elif endpoint_key == "charts_concurrent":
        return (
            "https://api.steampowered.com/ISteamChartsService/"
            "GetGamesByConcurrentPlayers/v1/?format=json"
        )
    else:
        raise ValueError(f"Unknown Steam endpoint key: {endpoint_key}")


def build_steam_appdetails_url(appid: str) -> str:
    safe_appid = quote(str(appid), safe="")
    return (
        "https://store.steampowered.com/api/appdetails"
        f"?appids={safe_appid}&cc={settings.steam_region}&l={settings.steam_language}&filters=basic"
    )


def parse_steam_date(date_str: str) -> date | None:
    """
    尝试以多种格式解析 Steam 返回的发布日期文本。
    支持中文形式 "2011年5月16日" 以及英文形式 "16 May, 2011" / "May 16, 2011"。
    """
    if not date_str:
        return None
    
    # 清理空格和换行
    date_str = re.sub(r"\s+", " ", date_str).strip()
    
    # 1. 中文匹配 "2024年6月29日"
    zh_m = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", date_str)
    if zh_m:
        try:
            return date(int(zh_m.group(1)), int(zh_m.group(2)), int(zh_m.group(3)))
        except ValueError:
            pass

    # 2. 英文匹配 "%d %b, %Y" 或 "%b %d, %Y" 等
    formats = [
        "%d %b, %Y",  # 16 May, 2011
        "%b %d, %Y",  # May 16, 2011
        "%Y-%m-%d",   # 2026-06-29
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            pass
            
    return None


def parse_steam_price(price_block: str) -> tuple[Decimal | None, Decimal | None]:
    """
    解析价格 HTML 段落，返回 (当前销售价, 原始标价)。
    若为免费游戏，均返回 0.00；若尚未定价或为空，均返回 None。
    """
    # 清理换行和多余空格
    block_clean = re.sub(r"\s+", " ", price_block).strip()
    
    # 判断是否为免费性质的字眼
    free_keywords = ["免费", "Free", "Free to Play", "免费开玩"]
    if any(kw in block_clean for kw in free_keywords):
        return Decimal("0.00"), Decimal("0.00")
        
    # 提取剥离标签后的纯文字
    plain_text = re.sub(r"<[^>]+>", " ", block_clean).strip()
    if not plain_text:
        return None, None

    original_m = re.search(
        r'<div\b[^>]*class="[^"]*\bdiscount_original_price\b[^"]*"[^>]*>[^<]*?([\d,.]+)[^<]*</div>',
        price_block,
        re.IGNORECASE,
    )
    final_m = re.search(
        r'<div\b[^>]*class="[^"]*\bdiscount_final_price\b[^"]*"[^>]*>[^<]*?([\d,.]+)[^<]*</div>',
        price_block,
        re.IGNORECASE,
    )
    if final_m:
        try:
            curr_val = Decimal(final_m.group(1).replace(",", ""))
            orig_val = Decimal(original_m.group(1).replace(",", "")) if original_m else curr_val
            return curr_val, orig_val
        except (ValueError, ArithmeticError):
            pass
        
    # 1. 检查是否存在 strike 标签（原价标签），若存在则是打折状态
    strike_m = re.search(r"<strike>[^<]*?([\d,.]+)</strike>", price_block)
    if strike_m:
        try:
            # 提取原价
            orig_val = Decimal(strike_m.group(1).replace(",", ""))
            # 现价处于 strike 标签的后面
            after_strike = price_block[strike_m.end():]
            plain_after = re.sub(r"<[^>]+>", " ", after_strike).strip()
            current_m = re.search(r"([\d,.]+)", plain_after)
            if current_m:
                curr_val = Decimal(current_m.group(1).replace(",", ""))
                return curr_val, orig_val
            return orig_val, orig_val
        except (ValueError, ArithmeticError):
            pass
            
    # 2. 普通原价购买（无打折）
    nums = re.findall(r"([\d,.]+)", plain_text)
    if nums:
        try:
            val = Decimal(nums[0].replace(",", ""))
            return val, val
        except (ValueError, ArithmeticError):
            pass
            
    return None, None


def _extract_div_inner_by_class(html: str, class_name: str) -> str:
    start_match = re.search(
        rf'<div\b[^>]*class="[^"]*\b{re.escape(class_name)}\b[^"]*"[^>]*>',
        html,
        re.IGNORECASE,
    )
    if start_match is None:
        return ""

    depth = 1
    content_start = start_match.end()
    for token in re.finditer(r"</?div\b[^>]*>", html[content_start:], re.IGNORECASE):
        token_text = token.group(0).lower()
        if token_text.startswith("</div"):
            depth -= 1
            if depth == 0:
                return html[content_start : content_start + token.start()]
        else:
            depth += 1
    return html[content_start:]


def parse_steam_results_html(results_html: str) -> list[dict[str, Any]]:
    """
    从 Steam 搜索列表的 HTML 文本中解析每个游戏条目的基础数据。
    """
    if not results_html:
        return []
        
    parsed_items = []
    # 查找所有的游戏项，每一个游戏行都是一个 class 包含 search_result_row 的 a 标签
    row_pattern = re.compile(r'<a\s+([^>]*class="[^"]*search_result_row[^"]*"[^>]*)>(.*?)</a>', re.DOTALL)
    
    rank = 1
    for match in row_pattern.finditer(results_html):
        attr_text = match.group(1)
        inner_html = match.group(2)
        
        try:
            # 1. 提取 appid (external_id)
            appid_m = re.search(r'data-ds-appid="([^"]+)"', attr_text)
            external_id = appid_m.group(1) if appid_m else ""
            
            # 2. 提取购买链接/源链接
            href_m = re.search(r'href="([^"]+)"', attr_text)
            source_url = href_m.group(1) if href_m else ""
            
            # 兜底从链接匹配 appid
            if not external_id and source_url:
                app_id_backup = re.search(r"/app/(\d+)", source_url)
                if app_id_backup:
                    external_id = app_id_backup.group(1)
            
            if not external_id:
                # 无法获取有效 appid，跳过此条目
                continue
                
            # 3. 提取名称 (name)
            name_m = re.search(r'<span class="title">([^<]+)</span>', inner_html)
            name = name_m.group(1).strip() if name_m else ""
            if not name:
                continue
                
            # 4. 提取封面图 (cover_url)
            cover_m = re.search(r'<img[^>]+src="([^"]+)"', inner_html)
            cover_url = cover_m.group(1).strip() if cover_m else ""
            
            # 5. 提取发布日期
            release_m = re.search(r'<div class="[^"]*search_released[^"]*">([^<]*)</div>', inner_html)
            release_text = release_m.group(1).strip() if release_m else ""
            release_date = parse_steam_date(release_text)
            
            # 6. 提取折扣与价格信息
            discount_percent = 0
            discount_label = ""
            discount_m = re.search(r'<div class="[^"]*search_discount[^"]*">.*?<span>([^<]+)</span>', inner_html, re.DOTALL)
            if discount_m:
                discount_label = discount_m.group(1).strip() # 例如 '-50%'
                percent_digits = re.search(r"(\d+)", discount_label)
                if percent_digits:
                    discount_percent = int(percent_digits.group(1))
            else:
                pct_m = re.search(
                    r'<div\b[^>]*class="[^"]*\bdiscount_pct\b[^"]*"[^>]*>\s*([^<]+?)\s*</div>',
                    inner_html,
                    re.DOTALL | re.IGNORECASE,
                )
                data_discount_m = re.search(r'data-discount="(\d+)"', inner_html, re.IGNORECASE)
                if pct_m:
                    discount_label = pct_m.group(1).strip()
                    percent_digits = re.search(r"(\d+)", discount_label)
                    if percent_digits:
                        discount_percent = int(percent_digits.group(1))
                elif data_discount_m and int(data_discount_m.group(1)) > 0:
                    discount_percent = int(data_discount_m.group(1))
                    discount_label = f"-{discount_percent}%"
            
            # 价格区块解析
            price_html = _extract_div_inner_by_class(inner_html, "search_price_discount_combined")
            
            current_price, original_price = parse_steam_price(price_html)
            
            # 构造结果项
            item = {
                "external_id": external_id,
                "name": name,
                "source_url": source_url,
                "cover_url": cover_url,
                "rank": rank,
                "current_price": current_price,
                "original_price": original_price,
                "discount_percent": discount_percent,
                "discount_label": discount_label,
                "release_date": release_date,
                "metadata": {
                    "original_release_text": release_text,
                    "price_html_raw": price_html,
                }
            }
            parsed_items.append(item)
            rank += 1
            
        except Exception as exc:
            # 单个条目解析失败仅记录警告日志，保证其余条目顺利解析
            log_adapter_failure(
                provider="steam",
                operation="parse_single_item",
                stage="item_parse",
                exc=exc
            )
            
    return parsed_items


def parse_steam_charts_concurrent_response(
    payload: dict[str, Any],
    *,
    details_by_appid: dict[str, dict[str, Any]] | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """
    解析 Steam Charts 实时并发在线榜（GetGamesByConcurrentPlayers）。
    每行同时携带当前在线人数与今日峰值；score 取当前在线人数，
    与 Steam 页面默认排序一致，峰值放 metadata 供前端二次排序。
    """
    response = payload.get("response")
    if not isinstance(response, dict):
        return []

    last_update = response.get("last_update")
    ranks = response.get("ranks")
    if not isinstance(ranks, list):
        return []

    details_by_appid = details_by_appid or {}
    parsed_items: list[dict[str, Any]] = []
    for index, row in enumerate(ranks[:limit], start=1):
        if not isinstance(row, dict):
            continue
        appid = row.get("appid")
        if appid is None:
            continue

        external_id = str(appid)
        detail = details_by_appid.get(external_id) or {}
        name = str(detail.get("name") or f"Steam App {external_id}").strip()
        cover_url = str(detail.get("header_image") or detail.get("capsule_image") or detail.get("capsule_imagev5") or "").strip()
        source_url = str(detail.get("source_url") or f"https://store.steampowered.com/app/{external_id}/").strip()
        concurrent_in_game = row.get("concurrent_in_game")
        peak_in_game = row.get("peak_in_game")

        try:
            rank_int = int(row.get("rank"))
        except (TypeError, ValueError):
            rank_int = index

        try:
            concurrent_score = Decimal(str(concurrent_in_game)) if concurrent_in_game is not None else None
        except (ArithmeticError, ValueError):
            concurrent_score = None

        parsed_items.append(
            {
                "external_id": external_id,
                "name": name,
                "source_url": source_url,
                "cover_url": cover_url,
                "rank": rank_int,
                "current_price": None,
                "original_price": None,
                "discount_percent": 0,
                "discount_label": "",
                "release_date": None,
                "score": concurrent_score,
                "metadata": {
                    "concurrent_in_game": concurrent_in_game,
                    "peak_in_game": peak_in_game,
                    "last_update": last_update,
                },
            }
        )

    return parsed_items


def fetch_steam_dataset(endpoint_key: str) -> list[dict[str, Any]]:
    """
    请求并抓取 Steam 排行榜 HTML，解析返回游戏列表。
    """
    url = build_steam_url(endpoint_key)
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
    }
    
    # 代理设置
    proxy = None
    if settings.steam_proxy_url:
        proxy = settings.steam_proxy_url
        
    try:
        # 使用 observed_http_get 记录并发出请求
        resp = observed_http_get(
            httpx.get,
            url,
            provider="steam",
            operation=endpoint_key,
            host="store.steampowered.com",
            path=f"/search/results/{endpoint_key}",
            headers=headers,
            proxy=proxy,
            timeout=settings.steam_timeout_seconds,
            follow_redirects=True,
        )
        resp.raise_for_status()
        
        # 接口返回的应该是一个 json 字典，包含 success 和 results_html
        resp_data = resp.json()
        if not resp_data or resp_data.get("success") != 1:
            raise ValueError(f"Steam API success status is not 1: {resp_data}")
            
        html = resp_data.get("results_html", "")
        return parse_steam_results_html(html)
        
    except Exception as exc:
        log_adapter_failure(provider="steam", operation=endpoint_key, stage="fetch", exc=exc)
        raise exc
