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
    created_at: datetime
    updated_at: datetime


class ReorderRequest(BaseModel):
    items: list[dict[str, int]]
