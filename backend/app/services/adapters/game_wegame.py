# -*- coding: utf-8 -*-
from decimal import Decimal
from typing import Any


WEGAME_API_URL = "https://www.wegame.com.cn/api/rail/web/data_filter/game_info/filter"

WEGAME_ENDPOINTS = {
    "popular_this_week": {
        "rank_name": "popular_this_week",
        "extra_options": {"list_type": 4, "need_gray_game": False},
    },
    "this_week_most_purchase": {
        "rank_name": "this_week_most_purchase",
        "extra_options": {
            "list_type": 3,
            "need_hot_rank_compare": True,
            "only_open_sell": True,
            "need_gray_game": False,
        },
    },
    "discounts": {
        "rank_name": "discounts",
        "extra_options": {"only_open_sell": True, "need_gray_game": False},
    },
}

WEGAME_FILTERS = [
    "game_id",
    "e_game_name",
    "game_name",
    "name",
    "game_type",
    "category",
    "comments",
    "screenshots",
    "banner_icon_url",
    "logo_url",
    "poster_url_h",
    "poster_url_v",
    "poster_h_decorative",
    "3rd_class",
    "4th_class",
    "top_class",
    "sub_class",
    "tags",
    "show_prate",
    "is_testing",
    "testing_state",
    "release_config",
    "master_game_id",
    "latest_purchase_rank",
    "last_purchase_rank",
    "week_recommend_ratio",
    "month_recommend_ratio",
    "total_recommend_ratio",
    "is_mobile_simulator",
    "poster_h_color",
    "follow_type",
]


def map_wegame_entry_url(entry_url: str) -> str:
    if not entry_url.startswith("wegame://"):
        raise ValueError(f"Unsupported WeGame entry_url: {entry_url}")
    endpoint_key = entry_url.replace("wegame://", "", 1)
    if endpoint_key not in WEGAME_ENDPOINTS:
        raise ValueError(f"Unsupported WeGame endpoint key: {endpoint_key}")
    return endpoint_key


def build_wegame_payload(endpoint_key: str, *, start_page: int = 0, page_size: int = 50) -> dict[str, Any]:
    config = WEGAME_ENDPOINTS.get(endpoint_key)
    if config is None:
        raise ValueError(f"Unknown WeGame endpoint key: {endpoint_key}")
    return {
        "property": [],
        "rank_name": config["rank_name"],
        "sort_by_asc": False,
        "filters": WEGAME_FILTERS,
        "keyword": "",
        "search_field": [],
        "tags": [],
        "stamp": {"agent_client_language": "zh_CN"},
        "response_format": 0,
        "start_page": start_page,
        "items_per_pager": min(page_size, 50),
        "search_type": 0,
        "extra_options": config["extra_options"],
    }


def build_wegame_detail_url(game_id: str) -> str:
    return f"https://www.wegame.com.cn/rail/game_detail.html?game_id={game_id}"


def _to_int(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_decimal(value: Any) -> Decimal | None:
    try:
        if value in (None, ""):
            return None
        return Decimal(str(value))
    except (ArithmeticError, ValueError):
        return None


def parse_wegame_rank_response(payload: dict[str, Any], endpoint_key: str, *, limit: int = 50) -> list[dict[str, Any]]:
    items = payload.get("items")
    if not isinstance(items, list):
        return []

    parsed: list[dict[str, Any]] = []
    for index, row in enumerate(items[:limit], start=1):
        if not isinstance(row, dict):
            continue
        game_id = str(row.get("game_id") or "").strip()
        name = str(row.get("game_name") or row.get("name") or "").strip()
        if not game_id or not name:
            continue

        latest_purchase_rank = _to_int(row.get("latest_purchase_rank"))
        score = _to_decimal(row.get("week_recommend_ratio") or row.get("total_recommend_ratio"))
        cover_url = str(row.get("poster_url_h") or row.get("banner_icon_url") or row.get("logo_url") or "").strip()

        parsed.append(
            {
                "external_id": game_id,
                "name": name,
                "source_url": build_wegame_detail_url(game_id),
                "cover_url": cover_url,
                "rank": latest_purchase_rank or index,
                "current_price": None,
                "original_price": None,
                "discount_percent": 0,
                "discount_label": "",
                "release_date": None,
                "score": score,
                "ranking_type": endpoint_key,
                "metadata": {
                    "provider": "wegame",
                    "rank_name": endpoint_key,
                    "e_game_name": row.get("e_game_name") or "",
                    "comments": row.get("comments") or "",
                    "latest_purchase_rank": latest_purchase_rank,
                    "last_purchase_rank": _to_int(row.get("last_purchase_rank")),
                    "week_recommend_ratio": row.get("week_recommend_ratio") or "",
                    "month_recommend_ratio": row.get("month_recommend_ratio") or "",
                    "total_recommend_ratio": row.get("total_recommend_ratio") or "",
                    "show_prate": row.get("show_prate") or "",
                    "top_class": row.get("top_class") or "",
                    "sub_class": row.get("sub_class") or "",
                    "tags": row.get("tags") or [],
                },
            }
        )

    return parsed
