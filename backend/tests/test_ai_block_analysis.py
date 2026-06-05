import pytest
from sqlalchemy import inspect

from app.core.database import get_session
from app.services.ai_client import AIClient
from app.services.token_usage import estimate_tokens, extract_token_usage


def test_ai_block_analysis_tables_exist(client):
    session = next(client.app.dependency_overrides[get_session]())
    inspector = inspect(session.bind)
    block_columns = {col["name"] for col in inspector.get_columns("ai_block_analyses")}
    usage_columns = {col["name"] for col in inspector.get_columns("ai_token_usages")}
    job_columns = {col["name"] for col in inspector.get_columns("ai_generation_jobs")}

    assert {
        "page_route",
        "block_id",
        "block_title",
        "source_type",
        "data_hash",
        "status",
        "summary_points_json",
        "key_changes_json",
        "risk_points_json",
        "related_entities_json",
        "evidence_refs_json",
        "generated_by_user_id",
        "token_usage_id",
        "expires_at",
    }.issubset(block_columns)
    assert {
        "user_id",
        "model_config_id",
        "model_name",
        "usage_type",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "estimated",
        "request_status",
        "related_job_id",
        "related_block_analysis_id",
    }.issubset(usage_columns)
    assert {"user_id", "block_analysis_id"}.issubset(job_columns)


def test_ai_client_returns_json_and_usage():
    async def fake_post(payload):
        return {
            "choices": [{"message": {"content": "{\"summary_points\":[\"A\"]}"}}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
        }

    import asyncio

    client = AIClient("https://example.com", "key", "model-a", post_json=fake_post)
    result = asyncio.run(client.complete_json_with_usage("system", "user"))

    assert result.content == {"summary_points": ["A"]}
    assert result.usage == {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18}
    assert result.usage_estimated is False


def test_usage_estimation_when_provider_does_not_return_usage():
    usage = extract_token_usage({}, "abcd" * 100, "{\"a\":1}")
    assert usage["total_tokens"] > 0
    assert usage["estimated"] is True


def test_estimate_tokens_is_stable_for_short_text():
    assert estimate_tokens("abcdefgh") == 2
