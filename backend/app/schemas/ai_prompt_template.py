from datetime import datetime

from pydantic import BaseModel, Field


class AIPromptTemplateWrite(BaseModel):
    topic_slug: str = Field(min_length=1, max_length=80)
    content_class: str = Field(pattern="^(news|rank|event)$")
    topic_context: str = Field(default="", max_length=4000)
    extra_forbidden: str = Field(default="", max_length=2000)
    enabled: bool = True
    notes: str = Field(default="", max_length=1000)


class AIPromptTemplateRead(BaseModel):
    id: int
    topic_slug: str
    content_class: str
    topic_context: str
    extra_forbidden: str
    enabled: bool
    template_version: int
    updated_by_user_id: int | None
    notes: str
    created_at: datetime
    updated_at: datetime
