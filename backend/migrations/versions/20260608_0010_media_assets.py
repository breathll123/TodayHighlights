"""media assets

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-08
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa


revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    conn = op.get_bind()
    inspector = inspect(conn)
    return name in inspector.get_table_names()


def upgrade() -> None:
    if _table_exists("media_assets"):
        return

    op.create_table(
        "media_assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column("normalized_url", sa.String(length=1000), nullable=False),
        sa.Column("url_hash", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("asset_type", sa.String(length=40), nullable=False, server_default="image"),
        sa.Column("entity_type", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("entity_name", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("source_entity_id", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("original_filename", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("content_type", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("extension", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("local_path", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("public_path", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("fetch_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_fetched_at", sa.DateTime(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("url_hash", name="uq_media_assets_url_hash"),
    )
    op.create_index("ix_media_assets_status_asset", "media_assets", ["status", "asset_type"])
    op.create_index("ix_media_assets_entity", "media_assets", ["entity_type", "entity_name"])
    op.create_index("ix_media_assets_provider_last_used", "media_assets", ["provider", "last_used_at"])


def downgrade() -> None:
    if not _table_exists("media_assets"):
        return
    op.drop_index("ix_media_assets_provider_last_used", table_name="media_assets")
    op.drop_index("ix_media_assets_entity", table_name="media_assets")
    op.drop_index("ix_media_assets_status_asset", table_name="media_assets")
    op.drop_table("media_assets")
