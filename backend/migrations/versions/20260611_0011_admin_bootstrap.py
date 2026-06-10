"""admin bootstrap

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-11
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa


revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    tables = set(inspect(connection).get_table_names())

    if "topics" in tables:
        topics = sa.table(
            "topics",
            sa.column("name", sa.String()),
            sa.column("slug", sa.String()),
            sa.column("sort_order", sa.Integer()),
            sa.column("enabled", sa.Boolean()),
        )
        existing = connection.execute(
            sa.select(topics.c.slug).where(topics.c.slug == "stocks")
        ).first()
        if existing is None:
            op.bulk_insert(
                topics,
                [
                    {
                        "name": "股票",
                        "slug": "stocks",
                        "sort_order": 1,
                        "enabled": True,
                    }
                ],
            )

    if "app_settings" in tables:
        app_settings = sa.table(
            "app_settings",
            sa.column("key", sa.String()),
        )
        connection.execute(
            sa.delete(app_settings).where(app_settings.c.key == "admin.password")
        )


def downgrade() -> None:
    pass
