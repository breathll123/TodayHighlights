# -*- coding: utf-8 -*-
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.entities import GameDeal, GameItem, GameRanking, GameRawSnapshot, PageBlock
from app.services.blocks import resolve_block_data


def _session():
    # 创建内存 SQLite 数据库用于方块解析测试
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_resolve_game_blocks_empty() -> None:
    """测试在数据库无数据时，各个游戏方块解析器能优雅返回空列表 []"""
    with _session() as session:
        block_topsellers = PageBlock(source_type="game_top_sellers", display_count=5)
        block_specials = PageBlock(source_type="game_specials", display_count=5)
        block_new = PageBlock(source_type="game_new_releases", display_count=5)
        block_played = PageBlock(source_type="game_most_played", display_count=5)
        block_wegame = PageBlock(source_type="game_wegame_popular", display_count=5)

        assert resolve_block_data(session, block_topsellers) == []
        assert resolve_block_data(session, block_specials) == []
        assert resolve_block_data(session, block_new) == []
        assert resolve_block_data(session, block_played) == []
        assert resolve_block_data(session, block_wegame) == []


def test_resolve_game_ranking_blocks_with_data() -> None:
    """测试游戏排行榜方块解析"""
    with _session() as session:
        # 1. 准备主数据
        item1 = GameItem(provider="steam", external_id="1", name="Game A", last_seen_at=datetime.now())
        item2 = GameItem(provider="steam", external_id="2", name="Game B", last_seen_at=datetime.now())
        session.add_all([item1, item2])
        session.flush()

        # 2. 准备两批快照，测试它只取最新的一批
        snap_old = GameRawSnapshot(
            provider="steam", endpoint_key="top_sellers", request_url="", status_code=200,
            response_body=b"", response_hash="old", captured_at=datetime.utcnow() - timedelta(hours=2), parse_status="parsed"
        )
        snap_new = GameRawSnapshot(
            provider="steam", endpoint_key="top_sellers", request_url="", status_code=200,
            response_body=b"", response_hash="new", captured_at=datetime.utcnow(), parse_status="parsed"
        )
        session.add_all([snap_old, snap_new])
        session.flush()

        # 写入旧排行榜数据 (不应该被读取)
        ranking_old = GameRanking(
            provider="steam", ranking_type="top_sellers", game_item_id=item1.id, rank=2,
            captured_at=snap_old.captured_at, snapshot_id=snap_old.id
        )
        # 写入新排行榜数据 (应被读取)
        ranking_new = GameRanking(
            provider="steam", ranking_type="top_sellers", game_item_id=item2.id, rank=1,
            captured_at=snap_new.captured_at, snapshot_id=snap_new.id
        )
        session.add_all([ranking_old, ranking_new])
        
        # 写入对应新快照的价格数据
        deal_new = GameDeal(
            provider="steam", game_item_id=item2.id, currency="CNY", current_price=Decimal("68.00"),
            original_price=Decimal("98.00"), discount_percent=30, discount_label="-30%",
            captured_at=snap_new.captured_at, snapshot_id=snap_new.id
        )
        session.add(deal_new)
        session.commit()

        # 3. 运行 resolve_block_data 并进行验证
        block = PageBlock(source_type="game_top_sellers", display_count=5)
        res = resolve_block_data(session, block)
        
        assert len(res) == 1
        assert res[0]["title"] == "Game B"
        assert res[0]["rank"] == 1
        assert res[0]["current_price"] == 68.0
        assert res[0]["discount_label"] == "-30%"
        assert res[0]["captured_at"] == snap_new.captured_at.isoformat()


def test_resolve_game_ranking_ignores_latest_failed_snapshot() -> None:
    """最新快照失败时，页面应回退到最近一次成功解析的数据"""
    with _session() as session:
        item = GameItem(provider="steam", external_id="1", name="Game A", last_seen_at=datetime.now())
        session.add(item)
        session.flush()

        parsed_snap = GameRawSnapshot(
            provider="steam", endpoint_key="top_sellers", request_url="", status_code=200,
            response_body=b"", response_hash="parsed", captured_at=datetime.utcnow() - timedelta(hours=1),
            parse_status="parsed",
        )
        failed_snap = GameRawSnapshot(
            provider="steam", endpoint_key="top_sellers", request_url="", status_code=500,
            response_body=b"", response_hash="failed", captured_at=datetime.utcnow(),
            parse_status="failed",
        )
        session.add_all([parsed_snap, failed_snap])
        session.flush()

        session.add(
            GameRanking(
                provider="steam", ranking_type="top_sellers", game_item_id=item.id, rank=1,
                captured_at=parsed_snap.captured_at, snapshot_id=parsed_snap.id,
            )
        )
        session.commit()

        block = PageBlock(source_type="game_top_sellers", display_count=5)
        res = resolve_block_data(session, block)

        assert len(res) == 1
        assert res[0]["title"] == "Game A"
        assert res[0]["captured_at"] == parsed_snap.captured_at.isoformat()


def test_resolve_game_top_sellers_falls_back_to_deals_when_rankings_missing() -> None:
    """热销榜历史快照若只有价格明细，也应能展示列表"""
    with _session() as session:
        item = GameItem(provider="steam", external_id="1091500", name="Cyberpunk 2077", last_seen_at=datetime.now())
        session.add(item)
        session.flush()

        snap = GameRawSnapshot(
            provider="steam", endpoint_key="top_sellers", request_url="", status_code=200,
            response_body=b"", response_hash="deal-only", captured_at=datetime.utcnow(),
            parse_status="pending",
        )
        session.add(snap)
        session.flush()

        deal = GameDeal(
            provider="steam", game_item_id=item.id, currency="CNY", current_price=Decimal("89.40"),
            original_price=Decimal("298.00"), discount_percent=70, discount_label="-70%",
            captured_at=snap.captured_at, snapshot_id=snap.id,
        )
        session.add(deal)
        session.commit()

        block = PageBlock(source_type="game_top_sellers", display_count=5)
        res = resolve_block_data(session, block)

        assert len(res) == 1
        assert res[0]["title"] == "Cyberpunk 2077"
        assert res[0]["rank"] == 1
        assert res[0]["current_price"] == 89.4
        assert res[0]["discount_label"] == "-70%"


def test_resolve_game_top_sellers_skips_empty_latest_snapshot() -> None:
    """最新原始快照无明细时，应继续回退到最近一批有明细的数据"""
    with _session() as session:
        item = GameItem(provider="steam", external_id="1091500", name="Cyberpunk 2077", last_seen_at=datetime.now())
        session.add(item)
        session.flush()

        data_snap = GameRawSnapshot(
            provider="steam", endpoint_key="top_sellers", request_url="", status_code=200,
            response_body=b"", response_hash="with-data", captured_at=datetime.utcnow() - timedelta(minutes=5),
            parse_status="parsed",
        )
        empty_snap = GameRawSnapshot(
            provider="steam", endpoint_key="top_sellers", request_url="", status_code=200,
            response_body=b"", response_hash="empty", captured_at=datetime.utcnow(),
            parse_status="parsed",
        )
        session.add_all([data_snap, empty_snap])
        session.flush()

        session.add(
            GameDeal(
                provider="steam", game_item_id=item.id, currency="CNY", current_price=Decimal("89.40"),
                original_price=Decimal("298.00"), discount_percent=70, discount_label="-70%",
                captured_at=data_snap.captured_at, snapshot_id=data_snap.id,
            )
        )
        session.commit()

        block = PageBlock(source_type="game_top_sellers", display_count=5)
        res = resolve_block_data(session, block)

        assert len(res) == 1
        assert res[0]["title"] == "Cyberpunk 2077"
        assert res[0]["captured_at"] == data_snap.captured_at.isoformat()


def test_resolve_game_most_played_blocks_with_data() -> None:
    """测试 Steam 在线热玩榜方块解析"""
    with _session() as session:
        item = GameItem(
            provider="steam",
            external_id="730",
            name="Counter-Strike 2",
            cover_url="https://shared.fastly.steamstatic.com/cs2.jpg",
            metadata_json={"last_week_rank": 2, "peak_in_game": 1234567},
            last_seen_at=datetime.now(),
        )
        session.add(item)
        session.flush()

        snap = GameRawSnapshot(
            provider="steam", endpoint_key="most_played", request_url="", status_code=200,
            response_body=b"", response_hash="played", captured_at=datetime.utcnow(), parse_status="parsed"
        )
        session.add(snap)
        session.flush()

        ranking = GameRanking(
            provider="steam", ranking_type="most_played", game_item_id=item.id, rank=1,
            score=Decimal("1234567"), captured_at=snap.captured_at, snapshot_id=snap.id
        )
        session.add(ranking)
        session.commit()

        block = PageBlock(source_type="game_most_played", display_count=5)
        res = resolve_block_data(session, block)

        assert len(res) == 1
        assert res[0]["title"] == "Counter-Strike 2"
        assert res[0]["rank"] == 1
        assert res[0]["score"] == 1234567.0
        assert res[0]["peak_in_game"] == 1234567
        assert res[0]["last_week_rank"] == 2


def test_resolve_game_most_played_falls_back_to_raw_snapshot() -> None:
    """在线热玩榜若 ranking 明细缺失，也可从原始 JSON 快照兜底展示"""
    with _session() as session:
        snap = GameRawSnapshot(
            provider="steam",
            endpoint_key="most_played",
            request_url="",
            status_code=200,
            response_body=(
                b'{"response":{"rollup_date":1778457600,"ranks":[{"rank":1,"appid":730,'
                b'"last_week_rank":2,"peak_in_game":1234567}]}}'
            ),
            response_hash="played-raw",
            captured_at=datetime.utcnow(),
            parse_status="pending",
        )
        session.add(snap)
        session.commit()

        block = PageBlock(source_type="game_most_played", display_count=5)
        res = resolve_block_data(session, block)

        assert len(res) == 1
        assert res[0]["title"] == "Steam App 730"
        assert res[0]["rank"] == 1
        assert res[0]["score"] == 1234567.0
        assert res[0]["peak_in_game"] == 1234567
        assert res[0]["last_week_rank"] == 2


def test_resolve_wegame_ranking_blocks_with_data() -> None:
    """WeGame 榜单方块应从对应 provider/ranking_type 的最新快照读取数据"""
    with _session() as session:
        item = GameItem(
            provider="wegame",
            external_id="2001918",
            name="三角洲行动",
            source_url="https://www.wegame.com.cn/rail/game_detail.html?game_id=2001918",
            cover_url="https://wegame.gtimg.com/g.2001918-r.abc/info.jpg",
            metadata_json={
                "comments": "新一代战术射击品质标杆",
                "description_zh": "战术射击游戏，主打多人协作和高强度对抗。",
                "e_game_name": "Delta Force",
                "last_purchase_rank": 3,
                "week_recommend_ratio": 87,
            },
            last_seen_at=datetime.now(),
        )
        session.add(item)
        session.flush()

        snap = GameRawSnapshot(
            provider="wegame",
            endpoint_key="popular_this_week",
            request_url="",
            status_code=200,
            response_body=b"",
            response_hash="wegame",
            captured_at=datetime.utcnow(),
            parse_status="parsed",
        )
        session.add(snap)
        session.flush()

        session.add(
            GameRanking(
                provider="wegame",
                ranking_type="popular_this_week",
                game_item_id=item.id,
                rank=1,
                score=Decimal("87"),
                captured_at=snap.captured_at,
                snapshot_id=snap.id,
            )
        )
        session.commit()

        block = PageBlock(source_type="game_wegame_popular", display_count=5)
        res = resolve_block_data(session, block)

        assert len(res) == 1
        assert res[0]["title"] == "三角洲行动"
        assert res[0]["source"] == "WeGame"
        assert res[0]["summary"] == "战术射击游戏，主打多人协作和高强度对抗。"
        assert res[0]["e_game_name"] == "Delta Force"
        assert res[0]["last_purchase_rank"] == 3
        assert res[0]["week_recommend_ratio"] == 87


def test_resolve_game_specials_blocks_with_data() -> None:
    """测试游戏特惠方块解析"""
    with _session() as session:
        item = GameItem(provider="steam", external_id="10", name="Promo Game", last_seen_at=datetime.now())
        session.add(item)
        session.flush()

        snap = GameRawSnapshot(
            provider="steam", endpoint_key="specials", request_url="", status_code=200,
            response_body=b"", response_hash="special", captured_at=datetime.utcnow(), parse_status="parsed"
        )
        session.add(snap)
        session.flush()

        deal = GameDeal(
            provider="steam", game_item_id=item.id, currency="CNY", current_price=Decimal("45.00"),
            original_price=Decimal("90.00"), discount_percent=50, discount_label="-50%",
            captured_at=snap.captured_at, snapshot_id=snap.id
        )
        session.add(deal)
        session.commit()

        block = PageBlock(source_type="game_specials", display_count=5)
        res = resolve_block_data(session, block)

        assert len(res) == 1
        assert res[0]["title"] == "Promo Game"
        assert res[0]["current_price"] == 45.0
        assert res[0]["original_price"] == 90.0
        assert res[0]["discount_percent"] == 50
        assert res[0]["discount_label"] == "-50%"
        assert res[0]["rank"] == 1  # 自动计算的排行序号
