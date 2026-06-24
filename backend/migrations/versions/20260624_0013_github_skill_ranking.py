"""github skill ranking

Revision ID: 0013
Revises: 0012
Create Date: 2026-06-24

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "github_skill_repos",
        # GitHub repo id is the PK (stable, not autoincrement).
        sa.Column("id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("owner", sa.String(120), nullable=False, server_default=""),
        sa.Column("name", sa.String(160), nullable=False, server_default=""),
        sa.Column("url", sa.String(500), nullable=False, server_default=""),
        sa.Column("language", sa.String(60), nullable=False, server_default=""),
        sa.Column("topics_json", sa.JSON(), nullable=False),
        sa.Column("topics_matched_json", sa.JSON(), nullable=False),
        sa.Column("stars", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("forks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pushed_at", sa.DateTime(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("description_zh", sa.Text(), nullable=False),
        sa.Column("is_skill", sa.Boolean(), nullable=True),
        sa.Column("skill_kind", sa.String(30), nullable=False, server_default=""),
        sa.Column("classify_reason", sa.String(120), nullable=False, server_default=""),
        sa.Column("classified_by_model", sa.String(120), nullable=False, server_default=""),
        sa.Column("classified_at", sa.DateTime(), nullable=True),
        sa.Column("translated_by_model", sa.String(120), nullable=False, server_default=""),
        sa.Column("translated_at", sa.DateTime(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_github_skill_repos_skill_stars", "github_skill_repos", ["is_skill", "status", "stars"])

    op.create_table(
        "github_skill_stats",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("repo_id", sa.BigInteger(), nullable=False),
        sa.Column("stars", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("forks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["repo_id"], ["github_skill_repos.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_github_skill_stats_repo_captured", "github_skill_stats", ["repo_id", "captured_at"])


def downgrade() -> None:
    op.drop_table("github_skill_stats")
    op.drop_table("github_skill_repos")
