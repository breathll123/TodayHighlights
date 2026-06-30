# -*- coding: utf-8 -*-
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.entities import GameItem, GameRawSnapshot, GameRanking, GameDeal


def _session():
    # 创建内存 SQLite 数据库用于模型测试
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_game_models_persist() -> None:
    """测试游戏相关模型数据能够正常入库及检索"""
    with _session() as s:
        # 1. 插入 GameItem
        item = GameItem(
            provider="steam",
            external_id="105600",  # Terraria appid
            name="泰拉瑞亚",
            name_en="Terraria",
            slug="terraria",
            cover_url="https://steam.com/terraria.jpg",
            cover_local="images/terraria.jpg",
            source_url="https://store.steampowered.com/app/105600",
            developers_json=["Re-Logic"],
            publishers_json=["Re-Logic"],
            platforms_json=["windows", "mac", "linux"],
            tags_json=["Sandbox", "Survival"],
            release_date=date(2011, 5, 16),
            metadata_json={"steam_rating": 98},
            last_seen_at=datetime(2026, 6, 29, 12, 0, 0),
            status="active"
        )
        s.add(item)
        s.commit()
        
        db_item = s.query(GameItem).filter_by(external_id="105600").one()
        assert db_item.name == "泰拉瑞亚"
        assert db_item.developers_json == ["Re-Logic"]
        assert db_item.platforms_json == ["windows", "mac", "linux"]
        assert db_item.release_date == date(2011, 5, 16)
        
        # 2. 插入 GameRawSnapshot
        snapshot = GameRawSnapshot(
            provider="steam",
            endpoint_key="top_sellers",
            request_url="https://store.steampowered.com/search/?filter=topsellers",
            status_code=200,
            response_body=b"<html>Steam Topsellers</html>",
            response_hash="hash_topsellers_xyz",
            captured_at=datetime(2026, 6, 29, 12, 0, 0),
            parse_status="pending",
            error_message=""
        )
        s.add(snapshot)
        s.commit()
        
        db_snapshot = s.query(GameRawSnapshot).filter_by(response_hash="hash_topsellers_xyz").one()
        assert db_snapshot.status_code == 200
        assert db_snapshot.response_body == b"<html>Steam Topsellers</html>"
        
        # 3. 插入 GameRanking
        ranking = GameRanking(
            provider="steam",
            ranking_type="top_sellers",
            game_item_id=db_item.id,
            rank=1,
            score=Decimal("100.00"),
            captured_at=datetime(2026, 6, 29, 12, 0, 0),
            snapshot_id=db_snapshot.id
        )
        s.add(ranking)
        s.commit()
        
        db_ranking = s.query(GameRanking).filter_by(game_item_id=db_item.id).one()
        assert db_ranking.rank == 1
        assert db_ranking.score == Decimal("100.00")
        
        # 4. 插入 GameDeal
        deal = GameDeal(
            provider="steam",
            game_item_id=db_item.id,
            currency="CNY",
            current_price=Decimal("18.00"),
            original_price=Decimal("36.00"),
            discount_percent=50,
            discount_label="-50%",
            deal_url="https://store.steampowered.com/app/105600",
            captured_at=datetime(2026, 6, 29, 12, 0, 0),
            snapshot_id=db_snapshot.id
        )
        s.add(deal)
        s.commit()
        
        db_deal = s.query(GameDeal).filter_by(game_item_id=db_item.id).one()
        assert db_deal.current_price == Decimal("18.00")
        assert db_deal.original_price == Decimal("36.00")
        assert db_deal.discount_percent == 50


def test_game_item_unique_constraint() -> None:
    """验证相同 (provider, external_id) 必须触发唯一约束冲突异常"""
    with _session() as s:
        item1 = GameItem(
            provider="steam",
            external_id="105600",
            name="泰拉瑞亚",
            last_seen_at=datetime.now()
        )
        s.add(item1)
        s.commit()
        
        # 重复的唯一组合，应当报错
        item2 = GameItem(
            provider="steam",
            external_id="105600",
            name="泰拉瑞亚副本",
            last_seen_at=datetime.now()
        )
        s.add(item2)
        with pytest.raises(IntegrityError):
            s.commit()
        s.rollback()
        
        # 不同的 provider 但相同的 external_id 应该可以插入成功
        item3 = GameItem(
            provider="epic",
            external_id="105600",
            name="泰拉瑞亚(Epic)",
            last_seen_at=datetime.now()
        )
        s.add(item3)
        s.commit()
        assert s.query(GameItem).count() == 2


def test_game_cascade_deletion() -> None:
    """验证删除 GameItem / GameRawSnapshot 后能够级联删除对应的排名/价格数据"""
    with _session() as s:
        # 设置测试数据
        item = GameItem(provider="steam", external_id="105600", name="游戏", last_seen_at=datetime.now())
        s.add(item)
        s.commit()
        
        snapshot = GameRawSnapshot(
            provider="steam", endpoint_key="x", request_url="y", status_code=200,
            response_body=b"", response_hash="h", captured_at=datetime.now()
        )
        s.add(snapshot)
        s.commit()
        
        ranking = GameRanking(provider="steam", ranking_type="r", game_item_id=item.id, rank=1, captured_at=datetime.now(), snapshot_id=snapshot.id)
        deal = GameDeal(provider="steam", game_item_id=item.id, captured_at=datetime.now(), snapshot_id=snapshot.id)
        s.add_all([ranking, deal])
        s.commit()
        
        assert s.query(GameRanking).count() == 1
        assert s.query(GameDeal).count() == 1
        
        # 删除主表数据
        s.delete(item)
        s.commit()
        
        # 关联的排行与优惠数据应该被 CASCADE 自动删除
        assert s.query(GameRanking).count() == 0
        assert s.query(GameDeal).count() == 0
