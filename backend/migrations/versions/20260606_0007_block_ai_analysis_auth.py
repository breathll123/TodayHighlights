"""block ai analysis auth

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-06
"""
from typing import Sequence, Union
from alembic import op
from sqlalchemy import inspect

import sqlalchemy as sa


revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    conn = op.get_bind()
    inspector = inspect(conn)
    return name in inspector.get_table_names()


def upgrade() -> None:
    if not _table_exists("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("username", sa.String(length=80), nullable=False),
            sa.Column("email", sa.String(length=160), nullable=True),
            sa.Column("password_hash", sa.String(length=255), nullable=False),
            sa.Column("role", sa.String(length=20), nullable=False, server_default="user"),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
            sa.Column("last_login_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("username", name="uq_users_username"),
            sa.UniqueConstraint("email", name="uq_users_email"),
        )
        op.create_index("ix_users_role_status", "users", ["role", "status"])

    if not _table_exists("ai_block_analyses"):
        op.create_table(
            "ai_block_analyses",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("page_route", sa.String(length=80), nullable=False),
            sa.Column("block_id", sa.Integer(), sa.ForeignKey("page_blocks.id"), nullable=False),
            sa.Column("block_title", sa.String(length=120), nullable=False),
            sa.Column("source_type", sa.String(length=40), nullable=False),
            sa.Column("data_hash", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="processing"),
            sa.Column("summary_points_json", sa.JSON(), nullable=False),
            sa.Column("key_changes_json", sa.JSON(), nullable=False),
            sa.Column("risk_points_json", sa.JSON(), nullable=False),
            sa.Column("related_entities_json", sa.JSON(), nullable=False),
            sa.Column("evidence_refs_json", sa.JSON(), nullable=False),
            sa.Column("model_config_id", sa.Integer(), sa.ForeignKey("ai_model_configs.id"), nullable=True),
            sa.Column("generated_by_model", sa.String(length=160), nullable=False, server_default=""),
            sa.Column("generated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("token_usage_id", sa.Integer(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=False),
            sa.Column("generated_at", sa.DateTime(), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )
        op.create_index(
            "ix_ai_block_analysis_cache",
            "ai_block_analyses",
            ["page_route", "block_id", "data_hash", "status", "expires_at"],
        )
        op.create_index(
            "ix_ai_block_analysis_user_created",
            "ai_block_analyses",
            ["generated_by_user_id", "created_at"],
        )

    if not _table_exists("ai_token_usages"):
        op.create_table(
            "ai_token_usages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("model_config_id", sa.Integer(), sa.ForeignKey("ai_model_configs.id"), nullable=True),
            sa.Column("model_name", sa.String(length=160), nullable=False, server_default=""),
            sa.Column("usage_type", sa.String(length=40), nullable=False),
            sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("estimated", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("request_status", sa.String(length=30), nullable=False, server_default="success"),
            sa.Column("related_job_id", sa.Integer(), sa.ForeignKey("ai_generation_jobs.id"), nullable=True),
            sa.Column("related_block_analysis_id", sa.Integer(), sa.ForeignKey("ai_block_analyses.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_ai_token_usages_user_created", "ai_token_usages", ["user_id", "created_at"])
        op.create_index("ix_ai_token_usages_model_created", "ai_token_usages", ["model_config_id", "created_at"])
        op.create_index("ix_ai_token_usages_type_created", "ai_token_usages", ["usage_type", "created_at"])

        op.create_foreign_key(
            "fk_ai_block_analyses_token_usage",
            "ai_block_analyses",
            "ai_token_usages",
            ["token_usage_id"],
            ["id"],
        )

    # These columns are NOT created by Base.metadata.create_all(), so always try to add them
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_cols = {col["name"] for col in inspector.get_columns("ai_generation_jobs")}
    if "user_id" not in existing_cols:
        op.add_column("ai_generation_jobs", sa.Column("user_id", sa.Integer(), nullable=True))
    if "block_analysis_id" not in existing_cols:
        op.add_column("ai_generation_jobs", sa.Column("block_analysis_id", sa.Integer(), nullable=True))

    # Add FKs if columns were just added
    if "user_id" not in existing_cols:
        op.create_foreign_key("fk_ai_generation_jobs_user", "ai_generation_jobs", "users", ["user_id"], ["id"])
    if "block_analysis_id" not in existing_cols:
        op.create_foreign_key(
            "fk_ai_generation_jobs_block_analysis",
            "ai_generation_jobs",
            "ai_block_analyses",
            ["block_analysis_id"],
            ["id"],
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_cols = {col["name"] for col in inspector.get_columns("ai_generation_jobs")}
    if "block_analysis_id" in existing_cols:
        op.drop_constraint("fk_ai_generation_jobs_block_analysis", "ai_generation_jobs", type_="foreignkey")
    if "user_id" in existing_cols:
        op.drop_constraint("fk_ai_generation_jobs_user", "ai_generation_jobs", type_="foreignkey")
    if "block_analysis_id" in existing_cols:
        op.drop_column("ai_generation_jobs", "block_analysis_id")
    if "user_id" in existing_cols:
        op.drop_column("ai_generation_jobs", "user_id")

    if _table_exists("ai_token_usages"):
        op.drop_constraint("fk_ai_block_analyses_token_usage", "ai_block_analyses", type_="foreignkey")
        op.drop_table("ai_token_usages")
    if _table_exists("ai_block_analyses"):
        op.drop_table("ai_block_analyses")
    if _table_exists("users"):
        op.drop_table("users")
