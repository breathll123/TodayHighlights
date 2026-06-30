# -*- coding: utf-8 -*-
"""block theme field

Revision ID: 0017
Revises: 0016
Create Date: 2026-06-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 为 page_blocks 表物理添加 theme 列，默认值为 "default"，且不可为空
    op.add_column("page_blocks", sa.Column("theme", sa.String(length=40), nullable=False, server_default="default"))


def downgrade() -> None:
    # 回滚：删除 theme 列
    op.drop_column("page_blocks", "theme")
