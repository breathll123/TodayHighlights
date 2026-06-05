from sqlalchemy import inspect

from app.core.database import get_session


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
