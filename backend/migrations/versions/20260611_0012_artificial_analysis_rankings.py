"""artificial analysis rankings

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-11

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "aa_sync_runs",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("trigger_type", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=True),
        sa.Column("requested_datasets_json", sa.JSON(), nullable=False),
        sa.Column("completed_datasets_json", sa.JSON(), nullable=False),
        sa.Column("failed_datasets_json", sa.JSON(), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quota_tier", sa.String(30), nullable=False, server_default=""),
        sa.Column("quota_limit", sa.Integer(), nullable=True),
        sa.Column("quota_remaining", sa.Integer(), nullable=True),
        sa.Column("quota_reset_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_aa_sync_runs_status_created", "aa_sync_runs", ["status", "created_at"])
    op.create_index("ix_aa_sync_runs_trigger_created", "aa_sync_runs", ["trigger_type", "created_at"])

    op.create_table(
        "aa_raw_snapshots",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("sync_run_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("dataset_key", sa.String(50), nullable=False),
        sa.Column("endpoint", sa.String(500), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("http_status", sa.Integer(), nullable=False),
        sa.Column("response_headers_json", sa.JSON(), nullable=False),
        sa.Column("body_compressed", mysql.LONGBLOB(), nullable=False),
        sa.Column("compression", sa.String(20), nullable=False, server_default="gzip"),
        sa.Column("content_type", sa.String(120), nullable=False, server_default=""),
        sa.Column("body_sha256", sa.String(64), nullable=False),
        sa.Column("original_size_bytes", sa.Integer(), nullable=False),
        sa.Column("compressed_size_bytes", sa.Integer(), nullable=False),
        sa.Column("parse_status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("parse_error", sa.Text(), nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["sync_run_id"], ["aa_sync_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sync_run_id", "dataset_key", "page_number", name="uq_aa_snapshot_run_dataset_page"),
    )
    op.create_index("ix_aa_snapshots_dataset_captured", "aa_raw_snapshots", ["dataset_key", "captured_at"])
    op.create_index("ix_aa_snapshots_body_sha", "aa_raw_snapshots", ["body_sha256"])

    op.create_table(
        "aa_ranking_datasets",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("sync_run_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("dataset_key", sa.String(50), nullable=False),
        sa.Column("scope", sa.String(20), nullable=False, server_default="global"),
        sa.Column("score_type", sa.String(40), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="parsing"),
        sa.Column("source_tier", sa.String(30), nullable=False, server_default=""),
        sa.Column("source_version", sa.String(40), nullable=False, server_default=""),
        sa.Column("entry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_snapshot_ids_json", sa.JSON(), nullable=False),
        sa.Column("parser_warnings_json", sa.JSON(), nullable=False),
        sa.Column("data_sha256", sa.String(64), nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["sync_run_id"], ["aa_sync_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_aa_datasets_key_status_published", "aa_ranking_datasets", ["dataset_key", "status", "published_at"])
    op.create_index("ix_aa_datasets_key_hash", "aa_ranking_datasets", ["dataset_key", "data_sha256"])

    op.create_table(
        "aa_creator_regions",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("creator_external_id", sa.String(120), nullable=True),
        sa.Column("canonical_name", sa.String(200), nullable=False),
        sa.Column("normalized_name", sa.String(200), nullable=False),
        sa.Column("region_code", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("source", sa.String(30), nullable=False, server_default="observed"),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("creator_external_id", name="uq_aa_creator_external_id"),
        sa.UniqueConstraint("normalized_name", name="uq_aa_creator_normalized_name"),
    )

    op.create_table(
        "aa_ranking_entries",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("dataset_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("model_external_id", sa.String(120), nullable=False),
        sa.Column("model_slug", sa.String(200), nullable=False, server_default=""),
        sa.Column("model_name", sa.String(300), nullable=False),
        sa.Column("creator_external_id", sa.String(120), nullable=False, server_default=""),
        sa.Column("creator_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("creator_region", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("score", sa.Numeric(16, 6), nullable=True),
        sa.Column("score_type", sa.String(40), nullable=False),
        sa.Column("ci_95", sa.Numeric(16, 6), nullable=True),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("pricing_json", sa.JSON(), nullable=False),
        sa.Column("performance_json", sa.JSON(), nullable=False),
        sa.Column("source_url", sa.String(500), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["aa_ranking_datasets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dataset_id", "model_external_id", name="uq_aa_entry_dataset_model"),
    )
    op.create_index("ix_aa_entries_dataset_rank", "aa_ranking_entries", ["dataset_id", "rank"])
    op.create_index("ix_aa_entries_creator", "aa_ranking_entries", ["creator_external_id"])


def downgrade() -> None:
    op.drop_table("aa_ranking_entries")
    op.drop_table("aa_ranking_datasets")
    op.drop_table("aa_raw_snapshots")
    op.drop_table("aa_creator_regions")
    op.drop_table("aa_sync_runs")
