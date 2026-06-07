"""ai prompt templates

Revision ID: 20260607_0008
Revises: 20260606_0007
Create Date: 2026-06-07
"""
from typing import Sequence, Union
from alembic import op
from sqlalchemy import inspect

import sqlalchemy as sa


revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    conn = op.get_bind()
    inspector = inspect(conn)
    return name in inspector.get_table_names()


def upgrade() -> None:
    if not _table_exists("ai_prompt_templates"):
        op.create_table(
            "ai_prompt_templates",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("topic_slug", sa.String(length=80), nullable=False),
            sa.Column("content_class", sa.String(length=30), nullable=False),
            sa.Column("topic_context", sa.Text(), nullable=False),
            sa.Column("extra_forbidden", sa.Text(), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("template_version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("notes", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("topic_slug", "content_class", name="uq_ai_prompt_template_topic_class"),
        )
        op.create_index(
            "ix_ai_prompt_templates_enabled",
            "ai_prompt_templates",
            ["topic_slug", "content_class", "enabled"],
        )

        # Seed default templates (only when table was just created)
        templates = [
            {
                "topic_slug": "stocks",
                "content_class": "news",
                "topic_context": "分析股票资讯时关注：政策信号、业绩变化、公告影响、板块联动和市场情绪。注意区分一次性事件和趋势性变化。",
                "extra_forbidden": "不得给出买入、卖出、持有、加仓、减仓等操作建议；不得给出价格预测、涨跌预测或收益承诺。",
                "notes": "默认股票资讯模板",
            },
            {
                "topic_slug": "stocks",
                "content_class": "rank",
                "topic_context": "分析股票榜单和行情时关注：资金集中度、板块联动、龙头效应、异常涨跌幅、成交或资金流变化。",
                "extra_forbidden": "不得给出买入、卖出、持有、加仓、减仓等操作建议；不得给出价格预测、涨跌预测或收益承诺。",
                "notes": "默认股票榜单模板",
            },
            {
                "topic_slug": "football",
                "content_class": "event",
                "topic_context": "分析足球赛事时关注：赛果、比赛状态、时间节点、积分影响、排名变化、主客场因素和后续赛程。",
                "extra_forbidden": "不得预测比分，不得把未开赛比赛描述为已发生事实。",
                "notes": "默认足球赛事模板",
            },
            {
                "topic_slug": "football",
                "content_class": "rank",
                "topic_context": "分析足球积分榜或排行榜时关注：排名变化、积分差距、净胜球、晋级或保级压力、赛程影响。",
                "extra_forbidden": "不得预测比分，不得把未开赛比赛描述为已发生事实。",
                "notes": "默认足球榜单模板",
            },
            {
                "topic_slug": "ai",
                "content_class": "news",
                "topic_context": "分析 AI 资讯时关注：模型能力变化、产品发布、商业化进展、开源与闭源格局、监管动态和产业影响。",
                "extra_forbidden": "",
                "notes": "默认 AI 资讯模板",
            },
        ]
        op.bulk_insert(sa.table(
            "ai_prompt_templates",
            sa.column("topic_slug", sa.String),
            sa.column("content_class", sa.String),
            sa.column("topic_context", sa.Text),
            sa.column("extra_forbidden", sa.Text),
            sa.column("enabled", sa.Boolean),
            sa.column("template_version", sa.Integer),
            sa.column("notes", sa.Text),
        ), [{**row, "enabled": True, "template_version": 1} for row in templates])


def downgrade() -> None:
    if _table_exists("ai_prompt_templates"):
        op.drop_index("ix_ai_prompt_templates_enabled", table_name="ai_prompt_templates")
        op.drop_table("ai_prompt_templates")
