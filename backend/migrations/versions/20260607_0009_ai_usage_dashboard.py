"""ai usage dashboard

Revision ID: 20260607_0009
Revises: 20260607_0008
Create Date: 2026-06-07
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ai_token_usages", sa.Column("prompt_text", sa.Text(), nullable=False, server_default=""))
    op.add_column("ai_token_usages", sa.Column("completion_text", sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("ai_token_usages", "completion_text")
    op.drop_column("ai_token_usages", "prompt_text")
