import pytest

from app.services.ai_validation import validate_item_enrichment_payload, validate_topic_summary_payload


def test_validate_item_enrichment_payload_accepts_valid_json() -> None:
    result = validate_item_enrichment_payload(
        {
            "title": "资金关注新能源",
            "summary": "新能源板块出现资金关注，相关公告和快讯密集出现。",
            "tags": ["资金", "新能源"],
            "related_symbols": ["新能源"],
            "importance_score": 72,
            "focus_points": ["资金关注度提升"],
            "risk_points": ["短期波动仍需观察"],
        }
    )

    assert result.importance_score == 72
    assert result.tags == ["资金", "新能源"]


def test_validate_item_enrichment_payload_rejects_score_out_of_range() -> None:
    with pytest.raises(ValueError, match="importance_score"):
        validate_item_enrichment_payload(
            {
                "title": "资金关注新能源",
                "summary": "新能源板块出现资金关注，相关公告和快讯密集出现。",
                "tags": ["资金"],
                "related_symbols": [],
                "importance_score": 101,
                "focus_points": ["资金关注度提升"],
                "risk_points": [],
            }
        )


def test_validate_topic_summary_requires_three_to_five_items() -> None:
    with pytest.raises(ValueError, match="items"):
        validate_topic_summary_payload({"title": "股票今日看点", "items": []})
