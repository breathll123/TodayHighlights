"""ai enrichment tables

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-05
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. ai_model_configs ──
    op.create_table(
        "ai_model_configs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("base_url", sa.String(500), nullable=False),
        sa.Column("model", sa.String(160), nullable=False),
        sa.Column("api_key_encrypted", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── 2. ai_item_enrichments ──
    op.create_table(
        "ai_item_enrichments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("topic_id", sa.Integer(), sa.ForeignKey("topics.id"), nullable=False),
        sa.Column("raw_item_id", sa.Integer(), sa.ForeignKey("raw_items.id"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("generated_title", sa.String(300), nullable=False, server_default=""),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("tags_json", sa.JSON(), nullable=False),
        sa.Column("related_symbols_json", sa.JSON(), nullable=False),
        sa.Column("importance_score", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("focus_points_json", sa.JSON(), nullable=False),
        sa.Column("risk_points_json", sa.JSON(), nullable=False),
        sa.Column("model_config_id", sa.Integer(), sa.ForeignKey("ai_model_configs.id"), nullable=True),
        sa.Column("generated_by_model", sa.String(160), nullable=False, server_default=""),
        sa.Column("error_message", sa.Text(), nullable=False, server_default=""),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_attempted_at", sa.DateTime(), nullable=True),
        sa.Column("generated_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("raw_item_id", name="uq_ai_item_enrichment_raw_item"),
        sa.Index("ix_ai_item_enrichments_topic_status", "topic_id", "status", "importance_score"),
    )

    # ── 3. ai_topic_summaries ──
    op.create_table(
        "ai_topic_summaries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("topic_id", sa.Integer(), sa.ForeignKey("topics.id"), nullable=False),
        sa.Column("summary_date", sa.DateTime(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("status", sa.String(30), nullable=False, server_default="generated"),
        sa.Column("title", sa.String(120), nullable=False, server_default=""),
        sa.Column("items_json", sa.JSON(), nullable=False),
        sa.Column("source_refs_json", sa.JSON(), nullable=False),
        sa.Column("model_config_id", sa.Integer(), sa.ForeignKey("ai_model_configs.id"), nullable=True),
        sa.Column("generated_by_model", sa.String(160), nullable=False, server_default=""),
        sa.Column("error_message", sa.Text(), nullable=False, server_default=""),
        sa.Column("generated_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("topic_id", "summary_date", "version", name="uq_ai_topic_summary_version"),
        sa.Index("ix_ai_topic_summaries_topic_status", "topic_id", "status", "summary_date", "version"),
    )

    # ── 4. ai_generation_jobs ──
    op.create_table(
        "ai_generation_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_type", sa.String(40), nullable=False),
        sa.Column("trigger_type", sa.String(40), nullable=False),
        sa.Column("topic_id", sa.Integer(), sa.ForeignKey("topics.id"), nullable=True),
        sa.Column("raw_item_id", sa.Integer(), sa.ForeignKey("raw_items.id"), nullable=True),
        sa.Column("item_enrichment_id", sa.Integer(), sa.ForeignKey("ai_item_enrichments.id"), nullable=True),
        sa.Column("topic_summary_id", sa.Integer(), sa.ForeignKey("ai_topic_summaries.id"), nullable=True),
        sa.Column("model_config_id", sa.Integer(), sa.ForeignKey("ai_model_configs.id"), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("input_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("retry_of_job_id", sa.Integer(), sa.ForeignKey("ai_generation_jobs.id"), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=False, server_default=""),
        sa.Column("log_excerpt", sa.Text(), nullable=False, server_default=""),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_ai_generation_jobs_created", "created_at"),
        sa.Index("ix_ai_generation_jobs_status", "status", "job_type"),
    )


def downgrade() -> None:
    op.drop_table("ai_generation_jobs")
    op.drop_table("ai_topic_summaries")
    op.drop_table("ai_item_enrichments")
    op.drop_table("ai_model_configs")
