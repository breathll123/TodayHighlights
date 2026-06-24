"""skills platform — generic source-agnostic skill tables

Revision ID: 0014
Revises: 0013
Create Date: 2026-06-24

Replaces the GitHub-specific github_skill_repos/github_skill_stats with the
source-agnostic skills/skill_stats, migrating existing rows over (preserving
the cached LLM classification + Chinese translation, so we don't re-spend
tokens). The old GitHub tables are dropped after the data moves.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "skills",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("external_id", sa.String(120), nullable=False),
        sa.Column("name", sa.String(200), nullable=False, server_default=""),
        sa.Column("author", sa.String(160), nullable=False, server_default=""),
        sa.Column("url", sa.String(500), nullable=False, server_default=""),
        sa.Column("language", sa.String(60), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("description_zh", sa.Text(), nullable=False),
        sa.Column("popularity", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("popularity_kind", sa.String(20), nullable=False, server_default="stars"),
        sa.Column("extra_json", sa.JSON(), nullable=False),
        sa.Column("is_skill", sa.Boolean(), nullable=True),
        sa.Column("skill_kind", sa.String(30), nullable=False, server_default=""),
        sa.Column("classify_reason", sa.String(120), nullable=False, server_default=""),
        sa.Column("classify_prompt_version", sa.String(64), nullable=False, server_default=""),
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
        sa.UniqueConstraint("source", "external_id", name="uq_skills_source_external"),
    )
    op.create_index("ix_skills_kept_pop", "skills", ["is_skill", "status", "popularity"])

    op.create_table(
        "skill_stats",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("skill_id", sa.BigInteger(), nullable=False),
        sa.Column("popularity", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_skill_stats_skill_captured", "skill_stats", ["skill_id", "captured_at"])

    # Migrate existing GitHub rows (MySQL prod). Skipped on a fresh DB / SQLite
    # tests where the old tables never existed.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "github_skill_repos" in inspector.get_table_names():
        bind.execute(sa.text(
            """
            INSERT INTO skills
              (source, external_id, name, author, url, language, description, description_zh,
               popularity, popularity_kind, extra_json,
               is_skill, skill_kind, classify_reason, classify_prompt_version,
               classified_by_model, classified_at, translated_by_model, translated_at,
               first_seen_at, last_synced_at, status, created_at, updated_at)
            SELECT 'github', CAST(id AS CHAR), name, owner, url, language, description, description_zh,
               stars, 'stars',
               JSON_OBJECT('topics', topics_json, 'forks', forks, 'topics_matched', topics_matched_json),
               is_skill, skill_kind, classify_reason, '',
               classified_by_model, classified_at, translated_by_model, translated_at,
               first_seen_at, last_synced_at, status, created_at, updated_at
            FROM github_skill_repos
            """
        ))
        # Join on the numeric id (external_id holds the github repo id as a
        # string) to avoid a utf8mb4 collation clash between the column and the
        # CAST(... AS CHAR) result on MySQL 8.
        bind.execute(sa.text(
            """
            INSERT INTO skill_stats (skill_id, popularity, captured_at)
            SELECT s.id, st.stars, st.captured_at
            FROM github_skill_stats st
            JOIN skills s ON s.source = 'github' AND CAST(s.external_id AS UNSIGNED) = st.repo_id
            """
        ))
        op.drop_table("github_skill_stats")
        op.drop_table("github_skill_repos")


def downgrade() -> None:
    # The old GitHub-specific tables are not recreated (one-way generalization).
    op.drop_table("skill_stats")
    op.drop_table("skills")
