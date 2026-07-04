# -*- coding: utf-8 -*-
from decimal import Decimal

from app.services.adapters.game_wegame import (
    WEGAME_API_URL,
    build_wegame_payload,
    map_wegame_entry_url,
    parse_wegame_rank_response,
)


def test_map_wegame_entry_url() -> None:
    assert map_wegame_entry_url("wegame://popular_this_week") == "popular_this_week"
    assert map_wegame_entry_url("wegame://this_week_most_purchase") == "this_week_most_purchase"
    assert map_wegame_entry_url("wegame://discounts") == "discounts"


def test_build_wegame_payload() -> None:
    payload = build_wegame_payload("popular_this_week", page_size=15)

    assert WEGAME_API_URL.endswith("/api/rail/web/data_filter/game_info/filter")
    assert payload["rank_name"] == "popular_this_week"
    assert payload["items_per_pager"] == 15
    assert payload["extra_options"]["list_type"] == 4
    assert "game_id" in payload["filters"]
    assert payload["stamp"]["agent_client_language"] == "zh_CN"


def test_parse_wegame_rank_response() -> None:
    payload = {
        "result": {"error_code": 0, "error_message": ""},
        "total_items": 1,
        "items": [
            {
                "game_id": "2001918",
                "game_name": "三角洲行动",
                "e_game_name": "Delta Force",
                "comments": "新一代战术射击品质标杆",
                "poster_url_h": "https://wegame.gtimg.com/poster.jpg",
                "latest_purchase_rank": "2",
                "last_purchase_rank": "3",
                "week_recommend_ratio": "96.5",
                "tags": [{"name": "FPS"}],
            }
        ],
    }

    items = parse_wegame_rank_response(payload, "this_week_most_purchase")

    assert len(items) == 1
    assert items[0]["external_id"] == "2001918"
    assert items[0]["name"] == "三角洲行动"
    assert items[0]["rank"] == 2
    assert items[0]["cover_url"] == "https://wegame.gtimg.com/poster.jpg"
    assert items[0]["ranking_type"] == "this_week_most_purchase"
    assert items[0]["metadata"]["e_game_name"] == "Delta Force"
    assert items[0]["metadata"]["comments"] == "新一代战术射击品质标杆"
    assert items[0]["metadata"]["last_purchase_rank"] == 3


def test_parse_wegame_discount_prices_from_release_config() -> None:
    payload = {
        "result": {"error_code": 0, "error_message": ""},
        "total_items": 1,
        "items": [
            {
                "game_id": "3001",
                "game_name": "折扣游戏",
                "show_prate": "3折",
                "release_config": {
                    "price": 9900,
                    "discount_price": 2970,
                },
            }
        ],
    }

    items = parse_wegame_rank_response(payload, "discounts")

    assert len(items) == 1
    assert items[0]["current_price"] == Decimal("29.70")
    assert items[0]["original_price"] == Decimal("99")
    assert items[0]["discount_percent"] == 70
    assert items[0]["discount_label"] == "3折"
