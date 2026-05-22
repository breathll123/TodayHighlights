"""page_blocks

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "page_blocks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("page_route", sa.String(80), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("source_config", sa.JSON(), nullable=False),
        sa.Column("display_style", sa.String(40), nullable=False, server_default="card"),
        sa.Column("display_count", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("sort_by", sa.String(40), nullable=False, server_default="created_at"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_page_blocks_route_sort", "page_blocks", ["page_route", "sort_order"])


def downgrade() -> None:
    op.drop_index("ix_page_blocks_route_sort")
    op.drop_table("page_blocks")
