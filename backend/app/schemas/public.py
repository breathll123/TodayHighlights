from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class TopicRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    sort_order: int


class HighlightRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    summary: str
    related_symbols_json: list[str]
    tags_json: list[str]
    score: int
    is_pinned: bool
    created_at: datetime


class PageBlocksResponse(BaseModel):
    blocks: list[dict[str, Any]]


class AITopicSummaryItemRead(BaseModel):
    title: str
    reason: str
    related: list[str]
    risk: str
    source_refs: list[int]


class AITopicSummaryRead(BaseModel):
    title: str
    version: int
    generated_at: datetime | None
    items: list[AITopicSummaryItemRead]
