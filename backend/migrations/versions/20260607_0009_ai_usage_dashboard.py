"""ai usage dashboard

Revision ID: 20260607_0009
Revises: 20260607_0008
Create Date: 2026-06-07
"""
from typing import Sequence, Union
from alembic import op
from sqlalchemy import inspect

import sqlalchemy as sa


revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_cols = {col["name"] for col in inspector.get_columns("ai_token_usages")}
    if "prompt_text" not in existing_cols:
        op.add_column("ai_token_usages", sa.Column("prompt_text", sa.Text(), nullable=False))
    if "completion_text" not in existing_cols:
        op.add_column("ai_token_usages", sa.Column("completion_text", sa.Text(), nullable=False))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_cols = {col["name"] for col in inspector.get_columns("ai_token_usages")}
    if "completion_text" in existing_cols:
        op.drop_column("ai_token_usages", "completion_text")
    if "prompt_text" in existing_cols:
        op.drop_column("ai_token_usages", "prompt_text")
