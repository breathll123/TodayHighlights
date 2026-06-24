from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (BigInteger, Boolean, Date, DateTime, ForeignKey, Index, Integer, JSON,
                        LargeBinary, Numeric, String, Text, UniqueConstraint, func)
from sqlalchemy.dialects.mysql import LONGBLOB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

BIGINT_PK = BigInteger().with_variant(Integer, "sqlite")
RAW_BODY_TYPE = LargeBinary().with_variant(LONGBLOB(), "mysql")


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class Topic(TimestampMixin, Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    sources: Mapped[list["Source"]] = relationship(back_populates="topic")
    highlights: Mapped[list["Highlight"]] = relationship(back_populates="topic")


class Source(TimestampMixin, Base):
    __tablename__ = "sources"
    __table_args__ = (
        Index("ix_sources_site", "site"),
        Index("ix_sources_next_crawl", "enabled", "next_crawl_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), nullable=False)
    site: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    entry_url: Mapped[str] = mapped_column(String(500), nullable=False)
    cookie_encrypted: Mapped[str] = mapped_column(Text, default="", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    crawl_interval_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    last_crawled_at: Mapped[datetime | None] = mapped_column(DateTime)
    next_crawl_at: Mapped[datetime | None] = mapped_column(DateTime)
    enable_highlight: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    topic: Mapped[Topic] = relationship(back_populates="sources")
    jobs: Mapped[list["CrawlJob"]] = relationship(back_populates="source")
    raw_items: Mapped[list["RawItem"]] = relationship(back_populates="source")


class CrawlJob(Base):
    __tablename__ = "crawl_jobs"
    __table_args__ = (
        Index("ix_crawl_jobs_source_created", "source_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    items_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    items_saved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    log_excerpt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    source: Mapped[Source] = relationship(back_populates="jobs")


class RawItem(Base):
    __tablename__ = "raw_items"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_raw_item_external"),
        UniqueConstraint("source_id", "content_hash", name="uq_raw_item_hash"),
        Index("ix_raw_items_source_published", "source_id", "published_at"),
        Index("ix_raw_items_status_expires", "status", "expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    author: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    title: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # Lifecycle fields
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    # Raw snapshot — original HTTP response for debugging / re-parsing
    raw_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    source: Mapped[Source] = relationship(back_populates="raw_items")
    highlights: Mapped[list["Highlight"]] = relationship(back_populates="raw_item")


class Highlight(TimestampMixin, Base):
    __tablename__ = "highlights"
    __table_args__ = (
        Index("ix_highlights_topic_score", "topic_id", "is_hidden", "is_pinned", "score"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), nullable=False)
    raw_item_id: Mapped[int] = mapped_column(ForeignKey("raw_items.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    related_symbols_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    tags_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    review_status: Mapped[str] = mapped_column(String(30), default="generated", nullable=False)
    generated_by_model: Mapped[str] = mapped_column(String(120), default="", nullable=False)

    topic: Mapped[Topic] = relationship(back_populates="highlights")
    raw_item: Mapped[RawItem] = relationship(back_populates="highlights")


class MediaAsset(TimestampMixin, Base):
    __tablename__ = "media_assets"
    __table_args__ = (
        UniqueConstraint("url_hash", name="uq_media_assets_url_hash"),
        Index("ix_media_assets_status_asset", "status", "asset_type"),
        Index("ix_media_assets_entity", "entity_type", "entity_name"),
        Index("ix_media_assets_provider_last_used", "provider", "last_used_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    normalized_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    asset_type: Mapped[str] = mapped_column(String(40), default="image", nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    entity_name: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    source_entity_id: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    extension: Mapped[str] = mapped_column(String(16), default="", nullable=False)
    local_path: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    public_path: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    fetch_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("username", name="uq_users_username"),
        UniqueConstraint("email", name="uq_users_email"),
        Index("ix_users_role_status", "role", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), nullable=False)
    email: Mapped[str | None] = mapped_column(String(160), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)


class AIBlockAnalysis(TimestampMixin, Base):
    __tablename__ = "ai_block_analyses"
    __table_args__ = (
        Index("ix_ai_block_analysis_cache", "page_route", "block_id", "data_hash", "status", "expires_at"),
        Index("ix_ai_block_analysis_user_created", "generated_by_user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    page_route: Mapped[str] = mapped_column(String(80), nullable=False)
    block_id: Mapped[int] = mapped_column(ForeignKey("page_blocks.id"), nullable=False)
    block_title: Mapped[str] = mapped_column(String(120), nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    data_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="processing", nullable=False)
    summary_points_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    key_changes_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    risk_points_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    related_entities_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    evidence_refs_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    model_config_id: Mapped[int | None] = mapped_column(ForeignKey("ai_model_configs.id"))
    generated_by_model: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    generated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    token_usage_id: Mapped[int | None] = mapped_column(ForeignKey("ai_token_usages.id"))
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)


class AITokenUsage(Base):
    __tablename__ = "ai_token_usages"
    __table_args__ = (
        Index("ix_ai_token_usages_user_created", "user_id", "created_at"),
        Index("ix_ai_token_usages_model_created", "model_config_id", "created_at"),
        Index("ix_ai_token_usages_type_created", "usage_type", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    model_config_id: Mapped[int | None] = mapped_column(ForeignKey("ai_model_configs.id"))
    model_name: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    usage_type: Mapped[str] = mapped_column(String(40), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    request_status: Mapped[str] = mapped_column(String(30), default="success", nullable=False)
    related_job_id: Mapped[int | None] = mapped_column(ForeignKey("ai_generation_jobs.id"))
    related_block_analysis_id: Mapped[int | None] = mapped_column(ForeignKey("ai_block_analyses.id"))
    prompt_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    completion_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class AIModelConfig(TimestampMixin, Base):
    __tablename__ = "ai_model_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    model: Mapped[str] = mapped_column(String(160), nullable=False)
    api_key_encrypted: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)


class AIPromptTemplate(TimestampMixin, Base):
    __tablename__ = "ai_prompt_templates"
    __table_args__ = (
        UniqueConstraint("topic_slug", "content_class", name="uq_ai_prompt_template_topic_class"),
        Index("ix_ai_prompt_templates_enabled", "topic_slug", "content_class", "enabled"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_slug: Mapped[str] = mapped_column(String(80), nullable=False)
    content_class: Mapped[str] = mapped_column(String(30), nullable=False)
    topic_context: Mapped[str] = mapped_column(Text, default="", nullable=False)
    extra_forbidden: Mapped[str] = mapped_column(Text, default="", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    template_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)


class AIItemEnrichment(TimestampMixin, Base):
    __tablename__ = "ai_item_enrichments"
    __table_args__ = (
        UniqueConstraint("raw_item_id", name="uq_ai_item_enrichment_raw_item"),
        Index("ix_ai_item_enrichments_topic_status", "topic_id", "status", "importance_score"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), nullable=False)
    raw_item_id: Mapped[int] = mapped_column(ForeignKey("raw_items.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    generated_title: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    tags_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    related_symbols_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    importance_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    focus_points_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    risk_points_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    model_config_id: Mapped[int | None] = mapped_column(ForeignKey("ai_model_configs.id"))
    generated_by_model: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_attempted_at: Mapped[datetime | None] = mapped_column(DateTime)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime)


class AITopicSummary(TimestampMixin, Base):
    __tablename__ = "ai_topic_summaries"
    __table_args__ = (
        UniqueConstraint("topic_id", "summary_date", "version", name="uq_ai_topic_summary_version"),
        Index("ix_ai_topic_summaries_topic_status", "topic_id", "status", "summary_date", "version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), nullable=False)
    summary_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="generated", nullable=False)
    title: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    items_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    source_refs_json: Mapped[list[int]] = mapped_column(JSON, default=list, nullable=False)
    model_config_id: Mapped[int | None] = mapped_column(ForeignKey("ai_model_configs.id"))
    generated_by_model: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime)


class AIGenerationJob(Base):
    __tablename__ = "ai_generation_jobs"
    __table_args__ = (
        Index("ix_ai_generation_jobs_created", "created_at"),
        Index("ix_ai_generation_jobs_status", "status", "job_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_type: Mapped[str] = mapped_column(String(40), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(40), nullable=False)
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id"))
    raw_item_id: Mapped[int | None] = mapped_column(ForeignKey("raw_items.id"))
    item_enrichment_id: Mapped[int | None] = mapped_column(ForeignKey("ai_item_enrichments.id"))
    topic_summary_id: Mapped[int | None] = mapped_column(ForeignKey("ai_topic_summaries.id"))
    model_config_id: Mapped[int | None] = mapped_column(ForeignKey("ai_model_configs.id"))
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    input_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    retry_of_job_id: Mapped[int | None] = mapped_column(ForeignKey("ai_generation_jobs.id"))
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    log_excerpt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    block_analysis_id: Mapped[int | None] = mapped_column(ForeignKey("ai_block_analyses.id"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class AppSetting(TimestampMixin, Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    value_encrypted: Mapped[str] = mapped_column(Text, default="", nullable=False)


class PageBlock(TimestampMixin, Base):
    __tablename__ = "page_blocks"
    __table_args__ = (
        Index("ix_page_blocks_route_status", "page_route", "enabled", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    page_route: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    display_style: Mapped[str] = mapped_column(String(40), default="card", nullable=False)
    display_count: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    sort_by: Mapped[str] = mapped_column(String(40), default="created_at", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    block_key: Mapped[str] = mapped_column(String(36), default="", nullable=False)
    col_span: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    row_span: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    grid_x: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    grid_y: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)


class AASyncRun(Base):
    __tablename__ = "aa_sync_runs"
    __table_args__ = (
        Index("ix_aa_sync_runs_status_created", "status", "created_at"),
        Index("ix_aa_sync_runs_trigger_created", "trigger_type", "created_at"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    trigger_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    requested_by_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    requested_datasets_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    completed_datasets_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    failed_datasets_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quota_tier: Mapped[str] = mapped_column(String(30), default="", nullable=False)
    quota_limit: Mapped[int | None] = mapped_column(Integer)
    quota_remaining: Mapped[int | None] = mapped_column(Integer)
    quota_reset_at: Mapped[datetime | None] = mapped_column(DateTime)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class AARawSnapshot(Base):
    __tablename__ = "aa_raw_snapshots"
    __table_args__ = (
        UniqueConstraint("sync_run_id", "dataset_key", "page_number", name="uq_aa_snapshot_run_dataset_page"),
        Index("ix_aa_snapshots_dataset_captured", "dataset_key", "captured_at"),
        Index("ix_aa_snapshots_body_sha", "body_sha256"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    sync_run_id: Mapped[int] = mapped_column(ForeignKey("aa_sync_runs.id"), nullable=False)
    dataset_key: Mapped[str] = mapped_column(String(50), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(500), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    http_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_headers_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    body_compressed: Mapped[bytes] = mapped_column(RAW_BODY_TYPE, nullable=False)
    compression: Mapped[str] = mapped_column(String(20), default="gzip", nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    body_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    original_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    compressed_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    parse_status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    parse_error: Mapped[str] = mapped_column(Text, default="", nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class AARankingDataset(Base):
    __tablename__ = "aa_ranking_datasets"
    __table_args__ = (
        Index("ix_aa_datasets_key_status_published", "dataset_key", "status", "published_at"),
        Index("ix_aa_datasets_key_hash", "dataset_key", "data_sha256"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    sync_run_id: Mapped[int] = mapped_column(ForeignKey("aa_sync_runs.id"), nullable=False)
    dataset_key: Mapped[str] = mapped_column(String(50), nullable=False)
    scope: Mapped[str] = mapped_column(String(20), default="global", nullable=False)
    score_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="parsing", nullable=False)
    source_tier: Mapped[str] = mapped_column(String(30), default="", nullable=False)
    source_version: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    entry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source_snapshot_ids_json: Mapped[list[int]] = mapped_column(JSON, default=list, nullable=False)
    parser_warnings_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    data_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class AARankingEntry(Base):
    __tablename__ = "aa_ranking_entries"
    __table_args__ = (
        UniqueConstraint("dataset_id", "model_external_id", name="uq_aa_entry_dataset_model"),
        Index("ix_aa_entries_dataset_rank", "dataset_id", "rank"),
        Index("ix_aa_entries_creator", "creator_external_id"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("aa_ranking_datasets.id"), nullable=False)
    model_external_id: Mapped[str] = mapped_column(String(120), nullable=False)
    model_slug: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    model_name: Mapped[str] = mapped_column(String(300), nullable=False)
    creator_external_id: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    creator_name: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    creator_region: Mapped[str] = mapped_column(String(20), default="unknown", nullable=False)
    rank: Mapped[int | None] = mapped_column(Integer)
    score: Mapped[Decimal | None] = mapped_column(Numeric(16, 6))
    score_type: Mapped[str] = mapped_column(String(40), nullable=False)
    ci_95: Mapped[Decimal | None] = mapped_column(Numeric(16, 6))
    release_date: Mapped[date | None] = mapped_column(Date)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    pricing_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    performance_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    source_url: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class AACreatorRegion(TimestampMixin, Base):
    __tablename__ = "aa_creator_regions"
    __table_args__ = (
        UniqueConstraint("creator_external_id", name="uq_aa_creator_external_id"),
        UniqueConstraint("normalized_name", name="uq_aa_creator_normalized_name"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    creator_external_id: Mapped[str | None] = mapped_column(String(120))
    canonical_name: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(200), nullable=False)
    region_code: Mapped[str] = mapped_column(String(20), default="unknown", nullable=False)
    source: Mapped[str] = mapped_column(String(30), default="observed", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)


class Skill(TimestampMixin, Base):
    """A source-agnostic skill record. Each provider (github, and future ones)
    upserts here keyed by (source, external_id). The current snapshot plus the
    cached LLM classification and Chinese description."""

    __tablename__ = "skills"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_skills_source_external"),
        Index("ix_skills_kept_pop", "is_skill", "status", "popularity"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False)            # "github"
    external_id: Mapped[str] = mapped_column(String(120), nullable=False)      # provider's stable id
    name: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    author: Mapped[str] = mapped_column(String(160), default="", nullable=False)  # owner/creator
    url: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    language: Mapped[str] = mapped_column(String(60), default="", nullable=False)

    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    description_zh: Mapped[str] = mapped_column(Text, default="", nullable=False)

    popularity: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)   # generic ranking metric (stars)
    popularity_kind: Mapped[str] = mapped_column(String(20), default="stars", nullable=False)
    extra_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)      # provider-specific (topics, forks, ...)

    # LLM classification (cached; recomputed on new / desc change / prompt change).
    is_skill: Mapped[bool | None] = mapped_column(Boolean)
    skill_kind: Mapped[str] = mapped_column(String(30), default="", nullable=False)
    classify_reason: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    classify_prompt_version: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    classified_by_model: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    classified_at: Mapped[datetime | None] = mapped_column(DateTime)

    translated_by_model: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    translated_at: Mapped[datetime | None] = mapped_column(DateTime)

    first_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)


class SkillStat(Base):
    """Daily popularity snapshot per skill — the time series behind the future
    day/week/month trend leaderboards (recorded from day one, not yet displayed)."""

    __tablename__ = "skill_stats"
    __table_args__ = (
        Index("ix_skill_stats_skill_captured", "skill_id", "captured_at"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), nullable=False)
    popularity: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
