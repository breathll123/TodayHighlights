"""page_blocks grid layout

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-23
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("page_blocks", sa.Column("block_key", sa.String(36), nullable=False, server_default=""))
    op.add_column("page_blocks", sa.Column("col_span", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("page_blocks", sa.Column("row_span", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("page_blocks", sa.Column("grid_x", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("page_blocks", sa.Column("grid_y", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("page_blocks", sa.Column("status", sa.String(20), nullable=False, server_default="draft"))


def downgrade() -> None:
    op.drop_column("page_blocks", "status")
    op.drop_column("page_blocks", "grid_y")
    op.drop_column("page_blocks", "grid_x")
    op.drop_column("page_blocks", "row_span")
    op.drop_column("page_blocks", "col_span")
    op.drop_column("page_blocks", "block_key")
