# -*- coding: utf-8 -*-
"""job log entries — per-job structured log timeline

Revision ID: 0015
Revises: 0014
Create Date: 2026-06-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# 迁移的修订版本号与上一个修订版本号（0014）
revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 新建任务日志表，记录爬取/分类过程中的结构化状态
    op.create_table(
        "job_log_entries",
        # 主键，在 SQLite 下是 Integer，MySQL 下是 BigInteger
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("crawl_job_id", sa.Integer(), nullable=False),
        sa.Column("ts", sa.DateTime(), nullable=False),
        sa.Column("level", sa.String(10), nullable=False, server_default="INFO"),
        sa.Column("channel", sa.String(20), nullable=False, server_default="application"),
        sa.Column("event", sa.String(80), nullable=False, server_default=""),
        sa.Column("category", sa.String(20), nullable=False, server_default=""),
        sa.Column("stage", sa.String(30), nullable=False, server_default=""),
        sa.Column("message", sa.Text(), nullable=False),  # TEXT 列不加 server_default，仅在 SQLAlchemy 模型层中提供默认值
        sa.Column("fields_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["crawl_job_id"], ["crawl_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    # 创建以任务 ID 为前导的多列联合索引，加速日志增量轮询查询
    op.create_index("ix_job_log_entries_job_id", "job_log_entries", ["crawl_job_id", "id"])


def downgrade() -> None:
    # 回滚：删除联合索引并删除表
    op.drop_index("ix_job_log_entries_job_id", table_name="job_log_entries")
    op.drop_table("job_log_entries")
