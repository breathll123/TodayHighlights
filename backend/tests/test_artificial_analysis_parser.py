from decimal import Decimal

import pytest

from app.models.entities import AACreatorRegion
from app.services.artificial_analysis.constants import DATASETS
from app.services.artificial_analysis.parser import (DatasetParseError, ParsedDataset, ParsedRankingEntry,
                                                       derive_china_dataset, normalize_creator_name,
                                                       parse_dataset, is_chinese_creator)


LANGUAGE_PAGE_1 = {
    "tier": "free",
    "intelligence_index_version": 4,
    "pagination": {"page": 1, "page_size": 2, "total_pages": 2, "has_more": True},
    "data": [
        {
            "id": "lang-qwen",
            "name": "Qwen 3",
            "slug": "qwen-3",
            "release_date": "2026-05-01",
            "model_creator": {"id": "creator-qwen", "name": "Qwen"},
            "evaluations": {
                "artificial_analysis_intelligence_index": 42.0,
                "artificial_analysis_coding_index": 39.0,
                "artificial_analysis_agentic_index": 40.0,
            },
            "artificial_analysis_intelligence_index_cost": {"total_cost": 12.5},
            "pricing": {"price_1m_input_tokens": 0.3, "price_1m_output_tokens": 1.2},
            "performance": {"median_output_tokens_per_second": 120.0},
        },
        {
            "id": "lang-global",
            "name": "Global Model",
            "slug": "global-model",
            "release_date": "2026-05-02",
            "model_creator": {"id": "creator-global", "name": "Global Labs"},
            "evaluations": {
                "artificial_analysis_intelligence_index": 45.0,
                "artificial_analysis_coding_index": 41.0,
                "artificial_analysis_agentic_index": 44.0,
            },
            "artificial_analysis_intelligence_index_cost": {"total_cost": 15.0},
            "pricing": {"price_1m_input_tokens": 0.5, "price_1m_output_tokens": 2.0},
            "performance": {"median_output_tokens_per_second": 100.0},
        },
    ],
}

LANGUAGE_PAGE_2 = {
    "tier": "free",
    "intelligence_index_version": 4,
    "pagination": {"page": 2, "page_size": 2, "total_pages": 2, "has_more": False},
    "data": [
        {
            "id": "lang-unknown",
            "name": "Independent Model",
            "slug": "independent-model",
            "release_date": "2026-04-20",
            "model_creator": None,
            "evaluations": {"artificial_analysis_intelligence_index": 35.0},
            "pricing": {},
            "performance": {},
        }
    ],
}


def arena_payload(
    model_id: str,
    model_name: str,
    creator_id: str,
    creator_name: str,
    elo: int,
    ci_95: int,
) -> dict:
    return {
        "tier": "free",
        "data": [
            {
                "id": model_id,
                "name": model_name,
                "slug": model_id,
                "model_creator": {"id": creator_id, "name": creator_name},
                "elo": elo,
                "ci_95": ci_95,
            }
        ],
    }


ARENA_PAYLOADS = {
    "text_to_image": arena_payload(
        "image-one", "Image One", "creator-image", "Image Labs", 1266, 11
    ),
    "text_to_video": arena_payload(
        "video-one", "Video One", "creator-video", "Video Labs", 1244, 13
    ),
    "image_to_video": arena_payload(
        "motion-one", "Motion One", "creator-motion", "Motion Labs", 1222, 15
    ),
    "text_to_speech": arena_payload(
        "voice-one", "Voice One", "creator-voice", "Voice Labs", 1200, 17
    ),
}

SPEECH_TO_TEXT = {
    "tier": "free",
    "data": [
        {
            "id": "stt-best",
            "name": "Best Transcriber",
            "model_creator": {"id": "creator-best", "name": "Best Labs"},
            "aa_wer_index": 0.08,
        },
        {
            "id": "stt-second",
            "name": "Second Transcriber",
            "model_creator": {"id": "creator-second", "name": "Second Labs"},
            "aa_wer_index": 0.12,
        },
    ],
}


def test_dataset_definitions_cover_first_release():
    assert set(DATASETS.keys()) == {
        "language_global", "text_to_image", "text_to_video",
        "image_to_video", "text_to_speech", "speech_to_text",
    }


def test_parse_language_pages_orders_intelligence_descending():
    parsed = parse_dataset("language_global", [LANGUAGE_PAGE_1, LANGUAGE_PAGE_2], [])
    assert len(parsed.entries) == 3
    # Highest score first
    assert parsed.entries[0].model_name == "Global Model"
    assert parsed.entries[0].rank == 1
    assert parsed.entries[0].score_type == "intelligence_index"
    assert parsed.entries[1].model_name == "Qwen 3"
    assert parsed.entries[1].rank == 2
    assert parsed.entries[2].model_name == "Independent Model"
    assert parsed.entries[2].rank == 3


def test_parse_media_arena_orders_elo_descending():
    parsed = parse_dataset("text_to_image", [ARENA_PAYLOADS["text_to_image"]], [])
    assert len(parsed.entries) == 1
    assert parsed.entries[0].model_name == "Image One"
    assert parsed.entries[0].score == pytest.approx(1266)
    assert parsed.entries[0].score_type == "elo"


def test_parse_speech_to_text_orders_wer_ascending():
    parsed = parse_dataset("speech_to_text", [SPEECH_TO_TEXT], [])
    assert len(parsed.entries) == 2
    # Lower WER = better → first
    assert parsed.entries[0].model_name == "Best Transcriber"
    assert parsed.entries[0].score == pytest.approx(Decimal("0.08"))
    assert parsed.entries[1].model_name == "Second Transcriber"
    assert parsed.entries[1].score == pytest.approx(Decimal("0.12"))


def test_creator_id_match_does_not_fall_back_to_name():
    regions = [
        AACreatorRegion(
            creator_external_id="creator-qwen",
            canonical_name="Qwen",
            normalized_name="qwen",
            region_code="cn",
            source="manual",
        )
    ]
    parsed = parse_dataset("language_global", [LANGUAGE_PAGE_1, LANGUAGE_PAGE_2], regions)
    qwen = next(e for e in parsed.entries if e.model_external_id == "lang-qwen")
    assert qwen.creator_region == "cn"
    # Global Model has a known ID not in our list → unknown
    global_m = next(e for e in parsed.entries if e.model_external_id == "lang-global")
    assert global_m.creator_region == "unknown"


def test_creator_name_fallback_requires_missing_id_and_exact_normalized_name():
    regions = [
        AACreatorRegion(
            creator_external_id=None,
            canonical_name="Independent Creator",
            normalized_name="independent creator",
            region_code="cn",
            source="manual",
        )
    ]
    parsed = parse_dataset("language_global", [LANGUAGE_PAGE_2], regions)
    indep = next(e for e in parsed.entries if e.model_external_id == "lang-unknown")
    # creator_id is absent, but model_creator is null — no name to match → unknown
    assert indep.creator_external_id == ""
    assert indep.creator_region == "unknown"


def test_unknown_creators_are_excluded_from_china_dataset():
    regions = [
        AACreatorRegion(
            creator_external_id="creator-qwen",
            canonical_name="Qwen",
            normalized_name="qwen",
            region_code="cn",
            source="manual",
        )
    ]
    parsed = parse_dataset("language_global", [LANGUAGE_PAGE_1, LANGUAGE_PAGE_2], regions)
    china = derive_china_dataset(parsed)
    assert len(china.entries) == 1
    assert china.entries[0].model_name == "Qwen 3"
    assert china.scope == "china"


def test_derive_china_dataset_reranks_models():
    regions = [
        AACreatorRegion(
            creator_external_id="creator-qwen",
            canonical_name="Qwen",
            normalized_name="qwen",
            region_code="cn",
            source="manual",
        ),
        AACreatorRegion(
            creator_external_id="creator-global",
            canonical_name="Global Labs",
            normalized_name="global labs",
            region_code="cn",
            source="manual",
        ),
    ]
    parsed = parse_dataset("language_global", [LANGUAGE_PAGE_1, LANGUAGE_PAGE_2], regions)
    china = derive_china_dataset(parsed)
    assert len(china.entries) == 2
    # Global Model has higher score → rank 1 in China set
    assert china.entries[0].model_name == "Global Model"
    assert china.entries[0].rank == 1
    assert china.entries[1].model_name == "Qwen 3"
    assert china.entries[1].rank == 2


def test_normalized_hash_is_stable():
    parsed1 = parse_dataset("language_global", [LANGUAGE_PAGE_1, LANGUAGE_PAGE_2], [])
    parsed2 = parse_dataset("language_global", [LANGUAGE_PAGE_1, LANGUAGE_PAGE_2], [])
    assert parsed1.data_sha256 == parsed2.data_sha256


def test_duplicate_model_id_keeps_first_row_and_records_warning():
    payload = {
        "tier": "free",
        "data": [
            {"id": "dup", "name": "First"},
            {"id": "dup", "name": "Second"},
        ],
    }
    parsed = parse_dataset("text_to_image", [payload], [])
    assert len(parsed.entries) == 1
    assert parsed.entries[0].model_name == "First"
    assert any("duplicate model_id" in w.lower() for w in parsed.warnings)


def test_more_than_ten_percent_invalid_rows_fails_dataset():
    payload = {
        "tier": "free",
        "data": [
            {"id": "a", "name": "Good"},
            None,  # invalid
            None,  # invalid
            None,  # invalid → 3/4 invalid = 75%
        ],
    }
    with pytest.raises(DatasetParseError):
        parse_dataset("text_to_image", [payload], [])


def test_normalize_creator_name_folds_case_and_whitespace():
    assert normalize_creator_name("  OpenAI  ") == "openai"
    assert normalize_creator_name("DeepSeek-AI") == "deepseek-ai"
    assert normalize_creator_name("") == ""


def test_is_chinese_creator_recognizes_z_ai():
    # 测试新增的 "Z AI" 及其变体能被成功识别为中国创作者
    assert is_chinese_creator("creator-z-ai", "Z AI") is True
    assert is_chinese_creator("z ai", "Zhipu Variant") is True
    # 测试已有关键字
    assert is_chinese_creator("deepseek-id", "DeepSeek") is True
    # 测试国外创作者
    assert is_chinese_creator("openai-id", "OpenAI") is False
    assert is_chinese_creator("", "") is False
