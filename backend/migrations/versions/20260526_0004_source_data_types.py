"""source data types

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-26
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("next_crawl_at", sa.DateTime(), nullable=True))
    op.add_column("sources", sa.Column("enable_highlight", sa.Boolean(), nullable=False, server_default="0"))

    # Update existing xueqiu sources to enable highlight
    op.execute("UPDATE sources SET enable_highlight = 1 WHERE site = 'xueqiu'")

    # Ensure a default topic exists so the seed sources have a valid topic_id
    op.execute("""
        INSERT INTO topics (id, name, slug, sort_order, enabled)
        SELECT 1, 'A股市场', 'a-stock', 0, 1
        WHERE NOT EXISTS (SELECT 1 FROM topics WHERE id = 1)
    """)

    # Seed Eastmoney + Tonghuashun sources
    op.execute("""
        INSERT INTO sources (topic_id, site, name, entry_url, cookie_encrypted, enabled, crawl_interval_minutes, enable_highlight)
        VALUES
        (1, 'eastmoney', '东方财富-概念板块', 'eastmoney://sectors', '', 1, 5, 0),
        (1, 'eastmoney', '东方财富-A股涨幅榜', 'eastmoney://gainers', '', 1, 5, 0),
        (1, 'eastmoney', '东方财富-行业板块', 'eastmoney://industry', '', 1, 5, 0),
        (1, 'eastmoney', '东方财富-主力资金流入', 'eastmoney://capital_flow', '', 1, 5, 0),
        (1, 'eastmoney', '东方财富-指数行情', 'eastmoney://indices', '', 1, 5, 0),
        (1, 'tonghuashun', '同花顺-财经快讯', 'tonghuashun://news', '', 1, 10, 0)
    """)


def downgrade() -> None:
    op.execute("DELETE FROM sources WHERE site IN ('eastmoney', 'tonghuashun')")
    op.drop_column("sources", "enable_highlight")
    op.drop_column("sources", "next_crawl_at")
