# -*- coding: utf-8 -*-
"""game domain tables — game_items, game_raw_snapshots, game_rankings, game_deals

Revision ID: 0016
Revises: 0015
Create Date: 2026-06-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# 迁移的修订版本号与上一个修订版本号（0015）
revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 创建游戏基础信息表 (game_items)
    op.create_table(
        "game_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("external_id", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("name_en", sa.String(length=255), server_default="", nullable=False),
        sa.Column("slug", sa.String(length=255), server_default="", nullable=False),
        sa.Column("cover_url", sa.Text(), nullable=False),
        sa.Column("cover_local", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("developers_json", sa.JSON(), nullable=False),
        sa.Column("publishers_json", sa.JSON(), nullable=False),
        sa.Column("platforms_json", sa.JSON(), nullable=False),
        sa.Column("tags_json", sa.JSON(), nullable=False),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "external_id", name="uq_game_items_provider_external_id")
    )
    # 创建最后看见时间与提供方的多列联合索引，加速数据抓取去重与查询
    op.create_index("ix_game_items_provider_last_seen", "game_items", ["provider", "last_seen_at"])

    # 2. 创建原始数据快照表 (game_raw_snapshots)
    op.create_table(
        "game_raw_snapshots",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("endpoint_key", sa.String(length=100), nullable=False),
        sa.Column("request_url", sa.Text(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("response_body", sa.LargeBinary().with_variant(sa.dialects.mysql.LONGBLOB(), "mysql"), nullable=False),
        sa.Column("response_hash", sa.String(length=64), nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.Column("parse_status", sa.String(length=30), server_default="pending", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id")
    )
    # 创建联合索引，用于按采集平台、端点和采集时间回溯
    op.create_index("ix_game_snapshots_lookup", "game_raw_snapshots", ["provider", "endpoint_key", "captured_at"])

    # 3. 创建游戏排行名次表 (game_rankings)
    op.create_table(
        "game_rankings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("ranking_type", sa.String(length=50), nullable=False),
        sa.Column("game_item_id", sa.Integer(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("score", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.Column("snapshot_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["game_item_id"], ["game_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["game_raw_snapshots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_game_rankings_lookup", "game_rankings", ["provider", "ranking_type", "captured_at"])
    op.create_index("ix_game_rankings_item_id", "game_rankings", ["game_item_id"])

    # 4. 创建打折特惠价格表 (game_deals)
    op.create_table(
        "game_deals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("game_item_id", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=10), server_default="CNY", nullable=False),
        sa.Column("current_price", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("original_price", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("discount_percent", sa.Integer(), server_default="0", nullable=False),
        sa.Column("discount_label", sa.String(length=50), server_default="", nullable=False),
        sa.Column("deal_url", sa.Text(), nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.Column("snapshot_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["game_item_id"], ["game_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["game_raw_snapshots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_game_deals_lookup", "game_deals", ["provider", "captured_at"])
    op.create_index("ix_game_deals_item_id", "game_deals", ["game_item_id"])


def downgrade() -> None:
    # 按照依赖关系，先删除外键子表，再删除主数据表
    op.drop_index("ix_game_deals_item_id", table_name="game_deals")
    op.drop_index("ix_game_deals_lookup", table_name="game_deals")
    op.drop_table("game_deals")

    op.drop_index("ix_game_rankings_item_id", table_name="game_rankings")
    op.drop_index("ix_game_rankings_lookup", table_name="game_rankings")
    op.drop_table("game_rankings")

    op.drop_index("ix_game_snapshots_lookup", table_name="game_raw_snapshots")
    op.drop_table("game_raw_snapshots")

    op.drop_index("ix_game_items_provider_last_seen", table_name="game_items")
    op.drop_table("game_items")
