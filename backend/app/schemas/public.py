from datetime import datetime

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
