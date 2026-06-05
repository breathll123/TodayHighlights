from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class SourceCreate(BaseModel):
    topic_id: int
    site: str
    name: str
    entry_url: str
    cookie: str = ""
    enabled: bool = True
    crawl_interval_minutes: int = 60


class SourceUpdate(BaseModel):
    topic_id: int | None = None
    site: str | None = None
    name: str | None = None
    entry_url: str | None = None
    cookie: str | None = None
    enabled: bool | None = None
    enable_highlight: bool | None = None
    crawl_interval_minutes: int | None = None


class SourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    topic_id: int
    site: str
    name: str
    entry_url: str
    enabled: bool
    crawl_interval_minutes: int
    last_crawled_at: datetime | None
    has_cookie: bool


class HighlightUpdate(BaseModel):
    title: str
    summary: str
    is_pinned: bool
    is_hidden: bool


class BlockCreate(BaseModel):
    page_route: str
    title: str
    sort_order: int = 0
    source_type: str
    source_config: dict[str, Any]
    display_style: str = "card"
    display_count: int = 5
    sort_by: str = "created_at"
    enabled: bool = True
    block_key: str = ""
    col_span: int = 1
    row_span: int = 1
    grid_x: int = 0
    grid_y: int = 0
    status: str = "draft"


class BlockUpdate(BaseModel):
    page_route: str | None = None
    title: str | None = None
    sort_order: int | None = None
    source_type: str | None = None
    source_config: dict[str, Any] | None = None
    display_style: str | None = None
    display_count: int | None = None
    sort_by: str | None = None
    enabled: bool | None = None
    block_key: str | None = None
    col_span: int | None = None
    row_span: int | None = None
    grid_x: int | None = None
    grid_y: int | None = None
    status: str | None = None


class BlockRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    page_route: str
    title: str
    sort_order: int
    source_type: str
    source_config: dict[str, Any]
    display_style: str
    display_count: int
    sort_by: str
    enabled: bool
    block_key: str
    col_span: int
    row_span: int
    grid_x: int
    grid_y: int
    status: str
    created_at: datetime
    updated_at: datetime


class ReorderRequest(BaseModel):
    items: list[dict[str, int]]


class AIModelConfigWrite(BaseModel):
    name: str
    base_url: str
    model: str
    api_key: str = ""
    is_default: bool = False
    enabled: bool = True
    notes: str = ""


class AIModelConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    base_url: str
    model: str
    is_default: bool
    enabled: bool
    notes: str
    has_api_key: bool
    created_at: datetime
    updated_at: datetime


class AIJobRead(BaseModel):
    id: int
    job_type: str
    trigger_type: str
    topic_id: int | None
    status: str
    input_count: int
    success_count: int
    failed_count: int
    error_message: str
    log_excerpt: str
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class AIJobListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[AIJobRead]
