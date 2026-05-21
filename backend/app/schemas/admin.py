from datetime import datetime

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
