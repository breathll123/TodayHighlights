# -*- coding: utf-8 -*-
import json
import os
from datetime import date
from decimal import Decimal

import pytest

from app.services.adapters.game_steam import (
    build_steam_appdetails_url,
    build_steam_url,
    parse_steam_most_played_response,
    parse_steam_date,
    parse_steam_price,
    parse_steam_results_html,
)


def test_build_steam_url() -> None:
    """测试不同数据端点的 URL 构建行为"""
    url_topsellers = build_steam_url("top_sellers")
    assert "filter=topsellers" in url_topsellers
    assert "cc=" in url_topsellers
    assert "l=" in url_topsellers

    url_specials = build_steam_url("specials")
    assert "specials=1" in url_specials

    url_new = build_steam_url("new_releases")
    assert "sort_by=Released_DESC" in url_new
    assert "filter=popularnew" not in url_new

    url_played = build_steam_url("most_played")
    assert "ISteamChartsService/GetMostPlayedGames" in url_played

    detail_url = build_steam_appdetails_url("730")
    assert "appdetails" in detail_url
    assert "appids=730" in detail_url

    with pytest.raises(ValueError):
        build_steam_url("unknown_endpoint")


def test_parse_steam_date() -> None:
    """测试多国语言发布日期的解析"""
    # 英文格式
    assert parse_steam_date("16 May, 2011") == date(2011, 5, 16)
    assert parse_steam_date("May 16, 2011") == date(2011, 5, 16)
    # 中文格式
    assert parse_steam_date("2024年6月29日") == date(2024, 6, 29)
    assert parse_steam_date("2024 年 06 月 29 日") == date(2024, 6, 29)
    # 模糊格式或非法格式应优雅返回 None
    assert parse_steam_date("2026年第4季度") is None
    assert parse_steam_date("") is None


def test_parse_steam_price() -> None:
    """测试各种价格及折扣 HTML 内容的解析"""
    # 1. 正常非折扣价格
    curr, orig = parse_steam_price('<div class="col search_price">¥ 36</div>')
    assert curr == Decimal("36.00")
    assert orig == Decimal("36.00")

    # 2. 折扣价格
    curr, orig = parse_steam_price(
        '<div class="col search_price discounted"><span><strike>¥ 128</strike></span><br>¥ 25.60</div>'
    )
    assert curr == Decimal("25.60")
    assert orig == Decimal("128.00")

    curr, orig = parse_steam_price(
        '<div class="discount_block search_discount_block" data-discount="90">'
        '<div class="discount_pct">-90%</div>'
        '<div class="discount_prices">'
        '<div class="discount_original_price">¥48.00</div>'
        '<div class="discount_final_price">¥4.80</div>'
        '</div></div>'
    )
    assert curr == Decimal("4.80")
    assert orig == Decimal("48.00")

    # 3. 免费性质的游戏
    curr, orig = parse_steam_price('<div class="col search_price">免费开玩</div>')
    assert curr == Decimal("0.00")
    assert orig == Decimal("0.00")

    # 4. 未定价游戏
    curr, orig = parse_steam_price('<div class="col search_price"></div>')
    assert curr is None
    assert orig is None


def _load_fixture(filename: str) -> str:
    path = os.path.join(os.path.dirname(__file__), "fixtures", filename)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data["results_html"]


def test_parse_topsellers_html() -> None:
    """从 fixture 解析热门销售游戏"""
    html = _load_fixture("steam_topsellers.json")
    items = parse_steam_results_html(html)
    
    assert len(items) == 2
    
    # 验证第一条 Terraria
    t = items[0]
    assert t["external_id"] == "105600"
    assert t["name"] == "Terraria"
    assert t["current_price"] == Decimal("36.00")
    assert t["original_price"] == Decimal("36.00")
    assert t["discount_percent"] == 0
    assert t["release_date"] == date(2011, 5, 16)
    assert t["rank"] == 1
    assert t["cover_url"] == "https://shared.fastly.steamstatic.com/terraria.jpg"
    
    # 验证第二条 Dota 2
    d = items[1]
    assert d["external_id"] == "570"
    assert d["name"] == "Dota 2"
    assert d["current_price"] == Decimal("0.00")
    assert d["original_price"] == Decimal("0.00")
    assert d["release_date"] == date(2013, 7, 9)
    assert d["rank"] == 2


def test_parse_specials_html() -> None:
    """从 fixture 解析折扣特卖游戏"""
    html = _load_fixture("steam_specials.json")
    items = parse_steam_results_html(html)
    
    assert len(items) == 1
    w = items[0]
    assert w["external_id"] == "292030"
    assert w["name"] == "The Witcher 3: Wild Hunt"
    assert w["current_price"] == Decimal("25.60")
    assert w["original_price"] == Decimal("128.00")
    assert w["discount_percent"] == 80
    assert w["discount_label"] == "-80%"
    assert w["rank"] == 1


def test_parse_current_steam_discount_markup() -> None:
    html = (
        '<a href="https://store.steampowered.com/app/1/Discount_Game/" '
        'class="search_result_row" data-ds-appid="1">'
        '<span class="title">Discount Game</span>'
        '<div class="col search_released">30 Jun, 2026</div>'
        '<div class="search_price_discount_combined responsive_secondrow" data-price-final="480">'
        '<div class="search_discount_and_price responsive_secondrow">'
        '<div class="discount_block search_discount_block" data-price-final="480" data-discount="90">'
        '<div class="discount_pct">-90%</div>'
        '<div class="discount_prices">'
        '<div class="discount_original_price">¥48.00</div>'
        '<div class="discount_final_price">¥4.80</div>'
        '</div></div></div></div>'
        '</a>'
    )
    items = parse_steam_results_html(html)

    assert len(items) == 1
    assert items[0]["discount_percent"] == 90
    assert items[0]["discount_label"] == "-90%"
    assert items[0]["current_price"] == Decimal("4.80")
    assert items[0]["original_price"] == Decimal("48.00")


def test_parse_new_releases_html() -> None:
    """从 fixture 解析新发布的未发售游戏"""
    html = _load_fixture("steam_new_releases.json")
    items = parse_steam_results_html(html)
    
    assert len(items) == 1
    u = items[0]
    assert u["external_id"] == "999999"
    assert u["name"] == "Upcoming Game"
    assert u["current_price"] is None
    assert u["original_price"] is None
    assert u["release_date"] is None
    assert u["metadata"]["original_release_text"] == "2026年第4季度"
    assert u["rank"] == 1


def test_parse_most_played_response() -> None:
    payload = {
        "response": {
            "rollup_date": 1778457600,
            "ranks": [
                {"rank": 1, "appid": 730, "last_week_rank": 2, "peak_in_game": 1234567},
            ],
        }
    }
    items = parse_steam_most_played_response(
        payload,
        details_by_appid={
            "730": {
                "name": "Counter-Strike 2",
                "header_image": "https://cdn.example/cs2.jpg",
            }
        },
    )

    assert len(items) == 1
    assert items[0]["external_id"] == "730"
    assert items[0]["name"] == "Counter-Strike 2"
    assert items[0]["cover_url"] == "https://cdn.example/cs2.jpg"
    assert items[0]["rank"] == 1
    assert items[0]["score"] == Decimal("1234567")
    assert items[0]["metadata"]["last_week_rank"] == 2
    assert items[0]["metadata"]["peak_in_game"] == 1234567


def test_parser_tolerates_corrupted_rows() -> None:
    """测试解析器能自动跳过损坏的 HTML 行并继续解析"""
    html = (
        # 正常条目
        '<a href="https://store.steampowered.com/app/1/" class="search_result_row" data-ds-appid="1">'
        '  <div class="responsive_search_name_combined"><span class="title">Good Game</span></div>'
        '</a>'
        # 缺少 appid 且无法从 href 提取的无效条目
        '<a class="search_result_row">'
        '  <div class="responsive_search_name_combined"><span class="title">No AppId</span></div>'
        '</a>'
        # 另一个正常条目
        '<a href="https://store.steampowered.com/app/2/" class="search_result_row" data-ds-appid="2">'
        '  <div class="responsive_search_name_combined"><span class="title">Another Good</span></div>'
        '</a>'
    )
    items = parse_steam_results_html(html)
    assert len(items) == 2
    assert items[0]["external_id"] == "1"
    assert items[1]["external_id"] == "2"
