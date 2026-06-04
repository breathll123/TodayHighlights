from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class RawItemDraft:
    external_id: str
    url: str
    author: str
    title: str
    body: str
    published_at: datetime | None
    metrics: dict[str, int | str] = field(default_factory=dict)
    content_hash: str = ""
    raw_snapshot: str = ""  # Original HTTP response body for debugging / re-parsing


class SourceAdapter(Protocol):
    def fetch(self, entry_url: str, cookie: str) -> list[RawItemDraft]:
        raise NotImplementedError
