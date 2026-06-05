from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ItemEnrichmentResult:
    title: str
    summary: str
    tags: list[str]
    related_symbols: list[str]
    importance_score: int
    focus_points: list[str]
    risk_points: list[str]


@dataclass(frozen=True)
class TopicSummaryItem:
    title: str
    reason: str
    related: list[str]
    risk: str
    source_refs: list[int]


@dataclass(frozen=True)
class TopicSummaryResult:
    title: str
    items: list[TopicSummaryItem]


def _require_str(value: Any, field: str, min_len: int, max_len: int) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    stripped = value.strip()
    if len(stripped) < min_len or len(stripped) > max_len:
        raise ValueError(f"{field} length must be {min_len}-{max_len}")
    return stripped


def _str_list(value: Any, field: str, max_items: int, item_max_len: int, min_items: int = 0) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    if len(value) < min_items or len(value) > max_items:
        raise ValueError(f"{field} length must be {min_items}-{max_items}")
    return [_require_str(item, field, 1, item_max_len) for item in value]


def validate_item_enrichment_payload(payload: dict[str, Any]) -> ItemEnrichmentResult:
    score = payload.get("importance_score")
    if not isinstance(score, int) or score < 0 or score > 100:
        raise ValueError("importance_score must be an integer from 0 to 100")
    return ItemEnrichmentResult(
        title=_require_str(payload.get("title"), "title", 1, 60),
        summary=_require_str(payload.get("summary"), "summary", 20, 180),
        tags=_str_list(payload.get("tags"), "tags", 5, 12),
        related_symbols=_str_list(payload.get("related_symbols"), "related_symbols", 10, 20),
        importance_score=score,
        focus_points=_str_list(payload.get("focus_points"), "focus_points", 3, 80, min_items=1),
        risk_points=_str_list(payload.get("risk_points"), "risk_points", 3, 80),
    )


def validate_topic_summary_payload(payload: dict[str, Any]) -> TopicSummaryResult:
    raw_items = payload.get("items")
    if not isinstance(raw_items, list) or len(raw_items) < 3 or len(raw_items) > 5:
        raise ValueError("items length must be 3-5")
    items = [
        TopicSummaryItem(
            title=_require_str(item.get("title"), "items.title", 1, 60),
            reason=_require_str(item.get("reason"), "items.reason", 20, 120),
            related=_str_list(item.get("related"), "items.related", 8, 20),
            risk=_require_str(item.get("risk", ""), "items.risk", 0, 100),
            source_refs=[int(ref) for ref in item.get("source_refs", [])[:10]],
        )
        for item in raw_items
    ]
    return TopicSummaryResult(title=_require_str(payload.get("title"), "title", 1, 40), items=items)
