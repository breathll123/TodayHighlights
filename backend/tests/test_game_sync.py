# -*- coding: utf-8 -*-
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.entities import CrawlJob, GameDeal, GameItem, GameRanking, GameRawSnapshot, Source, Topic
from app.services.game_sync import map_entry_url_to_endpoint, run_game_source_sync


def _session():
    # 创建内存 SQLite 数据库用于模型与同步测试
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


@pytest.fixture(autouse=True)
def _disable_media_cache(monkeypatch):
    """这些测试聚焦采集/解析/入库逻辑；媒体封面缓存有独立测试覆盖。

    在联网环境下，被 mock 的 httpx 会让封面下载在 safe_get 里走成重定向死循环，
    导致 MediaCacheService 回滚它的 _new_session()。生产环境该会话是独立的 MySQL
    连接、互不影响，但内存 SQLite 的单连接池会把这次回滚传导到调用方事务，冲掉尚未
    提交的快照 INSERT，从而在最终 commit 触发 StaleDataError。这里关闭媒体缓存以隔离。
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "steam_media_cache_limit", 0)


def test_map_entry_url_to_endpoint() -> None:
    """测试将伪协议 URL 映射为 Steam 的 endpoint_key"""
    assert map_entry_url_to_endpoint("steam://top_sellers") == "top_sellers"
    assert map_entry_url_to_endpoint("steam://specials") == "specials"
    assert map_entry_url_to_endpoint("steam://new_releases") == "new_releases"
    assert map_entry_url_to_endpoint("steam://most_played") == "most_played"
    assert map_entry_url_to_endpoint("wegame://popular_this_week") == "popular_this_week"
    assert map_entry_url_to_endpoint("wegame://this_week_most_purchase") == "this_week_most_purchase"
    assert map_entry_url_to_endpoint("wegame://discounts") == "discounts"

    with pytest.raises(ValueError):
        map_entry_url_to_endpoint("steam://unknown_endpoint")


@patch("httpx.Client")
def test_run_game_source_sync_topsellers(mock_client_class) -> None:
    """测试热门销售数据抓取与入库的同步完整流程"""
    # 模拟 Steam 热门榜的返回报文
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b'{"success": 1, "results_html": "<a href=\\"https://store.steampowered.com/app/105600/Terraria/\\" class=\\"search_result_row\\" data-ds-appid=\\"105600\\">\\n  <div class=\\"search_capsule\\"><img src=\\"https://shared.fastly.steamstatic.com/terraria.jpg\\"></div>\\n  <div class=\\"responsive_search_name_combined\\">\\n    <div class=\\"col search_name\\"><span class=\\"title\\">Terraria</span></div>\\n    <div class=\\"col search_released\\">16 May, 2011</div>\\n    <div class=\\"col search_price_discount_combined\\">\\n      <div class=\\"col search_price\\">\u00a5 36</div>\\n    </div>\\n  </div>\\n</a>"}'
    mock_response.json.return_repr = "MagicMock"
    mock_response.json.return_value = json_data = json_data = {
        "success": 1,
        "results_html": (
            '<a href="https://store.steampowered.com/app/105600/Terraria/" class="search_result_row" data-ds-appid="105600">\n'
            '  <div class="search_capsule"><img src="https://shared.fastly.steamstatic.com/terraria.jpg"></div>\n'
            '  <div class="responsive_search_name_combined">\n'
            '    <div class="col search_name"><span class="title">Terraria</span></div>\n'
            '    <div class="col search_released">16 May, 2011</div>\n'
            '    <div class="col search_price_discount_combined">\n'
            '      <div class="col search_price">¥ 36</div>\n'
            '    </div>\n'
            '  </div>\n'
            '</a>'
        )
    }

    mock_detail_response = MagicMock()
    mock_detail_response.status_code = 200
    mock_detail_response.json.return_value = {
        "105600": {
            "success": True,
            "data": {
                "short_description": "Dig, fight, explore, build! Nothing is impossible in this action-packed adventure game.",
                "header_image": "https://shared.fastly.steamstatic.com/terraria-header.jpg",
            },
        }
    }

    mock_client = MagicMock()
    mock_client.get.side_effect = [mock_response, mock_detail_response]
    mock_client_class.return_value.__enter__.return_value = mock_client

    with _session() as session:
        # 初始化测试实体
        topic = Topic(name="游戏", slug="games")
        session.add(topic)
        session.flush()

        source = Source(
            topic_id=topic.id,
            site="steam",
            name="Steam-热门游戏榜",
            entry_url="steam://top_sellers",
            crawl_interval_minutes=30
        )
        session.add(source)
        session.flush()

        job = CrawlJob(source_id=source.id, trigger_type="manual", status="running")
        session.add(job)
        session.flush()

        # 运行同步服务
        res = run_game_source_sync(session, source, job)

        assert res["found"] == 1
        assert res["saved"] == 1

        # 1. 验证快照正确存盘
        snapshot = session.scalar(select(GameRawSnapshot).where(GameRawSnapshot.endpoint_key == "top_sellers"))
        assert snapshot is not None
        assert snapshot.parse_status == "parsed"
        assert snapshot.status_code == 200

        # 2. 验证游戏项目主数据 upsert 成功
        game = session.scalar(select(GameItem).where(GameItem.external_id == "105600"))
        assert game is not None
        assert game.name == "Terraria"
        assert game.cover_url == "https://shared.fastly.steamstatic.com/terraria.jpg"
        assert game.metadata_json["description_original"].startswith("Dig, fight, explore")
        assert game.metadata_json["description_source"] == "steam_appdetails.short_description"

        # 3. 验证名次信息录入成功
        ranking = session.scalar(select(GameRanking).where(GameRanking.game_item_id == game.id))
        assert ranking is not None
        assert ranking.rank == 1
        assert ranking.snapshot_id == snapshot.id


@patch("httpx.Client")
def test_run_game_source_sync_specials(mock_client_class) -> None:
    """测试打折促销数据抓取与入库的同步完整流程"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "success": 1,
        "results_html": (
            '<a href="https://store.steampowered.com/app/292030/Witcher_3/" class="search_result_row" data-ds-appid="292030">\n'
            '  <div class="search_capsule"><img src="https://shared.fastly.steamstatic.com/witcher3.jpg"></div>\n'
            '  <div class="responsive_search_name_combined">\n'
            '    <div class="col search_name"><span class="title">The Witcher 3</span></div>\n'
            '    <div class="col search_released">18 May, 2015</div>\n'
            '    <div class="col search_price_discount_combined">\n'
            '      <div class="col search_discount"><span>-80%</span></div>\n'
            '      <div class="col search_price discounted"><span><strike>¥ 128</strike></span><br>¥ 25.60</div>\n'
            '    </div>\n'
            '  </div>\n'
            '</a>'
        )
    }

    mock_client = MagicMock()
    mock_client.get.return_value = mock_response
    mock_client_class.return_value.__enter__.return_value = mock_client

    with _session() as session:
        topic = Topic(name="游戏", slug="games")
        session.add(topic)
        session.flush()

        source = Source(
            topic_id=topic.id,
            site="steam",
            name="Steam-特惠",
            entry_url="steam://specials",
            crawl_interval_minutes=60
        )
        session.add(source)
        session.flush()

        job = CrawlJob(source_id=source.id, trigger_type="manual", status="running")
        session.add(job)
        session.flush()

        # 运行同步服务
        res = run_game_source_sync(session, source, job)

        assert res["found"] == 1
        assert res["saved"] == 1

        game = session.scalar(select(GameItem).where(GameItem.external_id == "292030"))
        assert game is not None
        assert game.name == "The Witcher 3"

        # 验证特惠数据录入
        deal = session.scalar(select(GameDeal).where(GameDeal.game_item_id == game.id))
        assert deal is not None
        assert deal.current_price == Decimal("25.60")
        assert deal.original_price == Decimal("128.00")
        assert deal.discount_percent == 80
        assert deal.discount_label == "-80%"


@patch("httpx.Client")
def test_run_game_source_sync_most_played(mock_client_class) -> None:
    """测试 Steam 在线热玩榜抓取与入库"""
    charts_response = MagicMock()
    charts_response.status_code = 200
    charts_response.content = (
        b'{"response":{"rollup_date":1778457600,"ranks":[{"rank":1,"appid":730,'
        b'"last_week_rank":2,"peak_in_game":1234567}]}}'
    )
    charts_response.json.return_value = {
        "response": {
            "rollup_date": 1778457600,
            "ranks": [
                {"rank": 1, "appid": 730, "last_week_rank": 2, "peak_in_game": 1234567},
            ],
        }
    }

    detail_response = MagicMock()
    detail_response.status_code = 200
    detail_response.json.return_value = {
        "730": {
            "success": True,
            "data": {
                "name": "Counter-Strike 2",
                "header_image": "https://shared.fastly.steamstatic.com/cs2.jpg",
            },
        }
    }

    mock_client = MagicMock()
    mock_client.get.side_effect = [charts_response, detail_response]
    mock_client_class.return_value.__enter__.return_value = mock_client

    with _session() as session:
        topic = Topic(name="游戏", slug="games")
        session.add(topic)
        session.flush()

        source = Source(
            topic_id=topic.id,
            site="steam",
            name="Steam-在线热玩榜",
            entry_url="steam://most_played",
            crawl_interval_minutes=30,
        )
        session.add(source)
        session.flush()

        job = CrawlJob(source_id=source.id, trigger_type="manual", status="running")
        session.add(job)
        session.flush()

        res = run_game_source_sync(session, source, job)

        assert res["found"] == 1
        assert res["saved"] == 1

        snapshot = session.scalar(select(GameRawSnapshot).where(GameRawSnapshot.endpoint_key == "most_played"))
        assert snapshot is not None
        assert snapshot.parse_status == "parsed"

        game = session.scalar(select(GameItem).where(GameItem.external_id == "730"))
        assert game is not None
        assert game.name == "Counter-Strike 2"
        assert game.cover_url == "https://shared.fastly.steamstatic.com/cs2.jpg"
        assert game.metadata_json["last_week_rank"] == 2
        assert game.metadata_json["peak_in_game"] == 1234567

        ranking = session.scalar(select(GameRanking).where(GameRanking.game_item_id == game.id))
        assert ranking is not None
        assert ranking.ranking_type == "most_played"
        assert ranking.rank == 1
        assert ranking.score == Decimal("1234567.00")


@patch("httpx.Client")
def test_run_game_source_sync_wegame_rank(mock_client_class) -> None:
    """测试 WeGame 榜单抓取与入库"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b'{"result":{"error_code":0,"error_message":""},"total_items":1,"items":[]}'
    mock_response.json.return_value = {
        "result": {"error_code": 0, "error_message": ""},
        "total_items": 1,
        "items": [
            {
                "game_id": "2001918",
                "game_name": "三角洲行动",
                "e_game_name": "Delta Force",
                "comments": "新一代战术射击品质标杆",
                "poster_url_h": "https://wegame.gtimg.com/poster.jpg",
                "latest_purchase_rank": "1",
                "last_purchase_rank": "2",
            }
        ],
    }

    mock_client = MagicMock()
    mock_client.post.return_value = mock_response
    mock_client_class.return_value.__enter__.return_value = mock_client

    with _session() as session:
        topic = Topic(name="游戏", slug="games")
        session.add(topic)
        session.flush()

        source = Source(
            topic_id=topic.id,
            site="wegame",
            name="WeGame-最高热度",
            entry_url="wegame://popular_this_week",
            crawl_interval_minutes=30,
        )
        session.add(source)
        session.flush()

        job = CrawlJob(source_id=source.id, trigger_type="manual", status="running")
        session.add(job)
        session.flush()

        res = run_game_source_sync(session, source, job)

        assert res["found"] == 1
        assert res["saved"] == 1

        snapshot = session.scalar(select(GameRawSnapshot).where(GameRawSnapshot.provider == "wegame"))
        assert snapshot is not None
        assert snapshot.endpoint_key == "popular_this_week"
        assert snapshot.parse_status == "parsed"

        game = session.scalar(select(GameItem).where(GameItem.provider == "wegame", GameItem.external_id == "2001918"))
        assert game is not None
        assert game.name == "三角洲行动"
        assert game.cover_url == "https://wegame.gtimg.com/poster.jpg"
        assert game.metadata_json["comments"] == "新一代战术射击品质标杆"
        assert game.metadata_json["description_original"] == "新一代战术射击品质标杆"
        assert game.metadata_json["description_zh"] == "新一代战术射击品质标杆"
        assert game.metadata_json["description_translated_by"] == "zh-native"

        ranking = session.scalar(select(GameRanking).where(GameRanking.provider == "wegame"))
        assert ranking is not None
        assert ranking.ranking_type == "popular_this_week"
        assert ranking.rank == 1
