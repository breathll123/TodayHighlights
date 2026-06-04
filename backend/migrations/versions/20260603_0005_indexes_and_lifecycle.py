"""indexes and lifecycle fields

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-03
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. New columns on raw_items ──
    op.add_column("raw_items", sa.Column("status", sa.String(20), nullable=False, server_default="active"))
    op.add_column("raw_items", sa.Column("expires_at", sa.DateTime(), nullable=True))
    op.add_column("raw_items", sa.Column("raw_snapshot", sa.Text(), nullable=True))

    # Backfill expires_at for existing rows (7 days from now)
    op.execute("""
        UPDATE raw_items
        SET expires_at = DATE_ADD(NOW(), INTERVAL 7 DAY)
        WHERE expires_at IS NULL
    """)

    # ── 2. New indexes ──

    # highlights: the most frequently hit query — topic block resolution
    op.create_index(
        "ix_highlights_topic_score",
        "highlights",
        ["topic_id", "is_hidden", "is_pinned", "score"],
    )

    # raw_items: source block queries + ordered listing
    op.create_index(
        "ix_raw_items_source_published",
        "raw_items",
        ["source_id", "published_at"],
    )

    # raw_items: cleanup / lifecycle queries
    op.create_index(
        "ix_raw_items_status_expires",
        "raw_items",
        ["status", "expires_at"],
    )

    # sources: block resolution looks up by site
    op.create_index("ix_sources_site", "sources", ["site"])

    # sources: scheduler checks enabled sources due for crawl (runs every minute!)
    op.create_index("ix_sources_next_crawl", "sources", ["enabled", "next_crawl_at"])

    # crawl_jobs: admin history view
    op.create_index(
        "ix_crawl_jobs_source_created",
        "crawl_jobs",
        ["source_id", "created_at"],
    )

    # page_blocks: replace old (route, sort_order) with full query coverage
    op.drop_index("ix_page_blocks_route_sort", table_name="page_blocks")
    op.create_index(
        "ix_page_blocks_route_status",
        "page_blocks",
        ["page_route", "enabled", "status"],
    )


def downgrade() -> None:
    # Drop new indexes
    op.drop_index("ix_page_blocks_route_status", table_name="page_blocks")
    op.create_index("ix_page_blocks_route_sort", "page_blocks", ["page_route", "sort_order"])

    op.drop_index("ix_crawl_jobs_source_created", table_name="crawl_jobs")
    op.drop_index("ix_sources_next_crawl", table_name="sources")
    op.drop_index("ix_sources_site", table_name="sources")
    op.drop_index("ix_raw_items_status_expires", table_name="raw_items")
    op.drop_index("ix_raw_items_source_published", table_name="raw_items")
    op.drop_index("ix_highlights_topic_score", table_name="highlights")

    # Drop new columns
    op.drop_column("raw_items", "raw_snapshot")
    op.drop_column("raw_items", "expires_at")
    op.drop_column("raw_items", "status")
