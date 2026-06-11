from datetime import datetime, timedelta

import pytest
from sqlalchemy import inspect

from app.core.config import settings
from app.core.crypto import CryptoService
from app.core.database import get_session
from app.models.entities import AIBlockAnalysis, AIModelConfig, AIPromptTemplate, PageBlock, Topic, User
from app.services.ai_block_analysis import analyze_block, build_block_data_hash, validate_block_analysis_payload
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


def _seed_user_model_block(session):
    user = User(username="alice", email=None, password_hash="hash", role="user", status="active")
    topic = Topic(name="股票", slug="stocks", enabled=True)
    session.add_all([user, topic])
    session.flush()
    block = PageBlock(
        page_route="/topics/stocks",
        title="热门资讯",
        source_type="topic",
        source_config={"topic_id": topic.id},
        display_count=5,
        sort_order=1,
        enabled=True,
        status="published",
    )
    key = CryptoService(settings.app_secret_key).encrypt("api-key")
    model = AIModelConfig(name="Default", base_url="https://example.com", model="free-model", api_key_encrypted=key, is_default=True, enabled=True)
    session.add_all([block, model])
    session.commit()
    return user, block


def test_validate_block_analysis_payload_bounds():
    payload = validate_block_analysis_payload(
        {
            "summary_points": ["核心内容"],
            "key_changes": ["变化"],
            "risk_points": ["风险"],
            "related_entities": ["A股"],
            "confidence": 0.7,
        }
    )
    assert payload.summary_points == ["核心内容"]
    assert payload.confidence == 0.7


def test_build_block_data_hash_is_stable():
    data = [{"title": "A", "summary": "B"}, {"summary": "D", "title": "C"}]
    assert build_block_data_hash(data) == build_block_data_hash(list(data))


def test_analyze_block_generates_and_records_token_usage(client):
    session = next(client.app.dependency_overrides[get_session]())
    user, block = _seed_user_model_block(session)

    async def fake_post(payload):
        return {
            "choices": [{"message": {"content": "{\"summary_points\":[\"多条内容集中在AI算力\"],\"key_changes\":[],\"risk_points\":[],\"related_entities\":[\"AI\"],\"confidence\":0.8}"}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
        }

    analysis = analyze_block(
        session,
        user=user,
        page_route="/topics/stocks",
        block_id=block.id,
        post_json=fake_post,
        resolved_data=[{"id": 1, "title": "AI算力走强", "summary": "相关公司活跃", "source": "测试源"}],
    )
    session.commit()

    assert analysis.status == "generated"
    assert analysis.generated_by_model == "free-model"
    assert analysis.summary_points_json == ["多条内容集中在AI算力"]
    assert analysis.token_usage_id is not None
    assert analysis.generated_by_user_id == user.id


def test_analyze_block_uses_valid_cache(client):
    session = next(client.app.dependency_overrides[get_session]())
    user, block = _seed_user_model_block(session)
    data = [{"id": 1, "title": "缓存内容", "summary": "不应调用模型"}]
    cached = AIBlockAnalysis(
        page_route="/topics/stocks",
        block_id=block.id,
        block_title=block.title,
        source_type=block.source_type,
        data_hash=build_block_data_hash(data),
        status="generated",
        summary_points_json=["缓存结果"],
        expires_at=datetime.utcnow() + timedelta(minutes=30),
    )
    session.add(cached)
    session.commit()

    async def fake_post(payload):
        raise AssertionError("cache hit should not call model")

    analysis = analyze_block(
        session,
        user=user,
        page_route="/topics/stocks",
        block_id=block.id,
        post_json=fake_post,
        resolved_data=data,
    )
    assert analysis.id == cached.id
    assert analysis.summary_points_json == ["缓存结果"]


from app.services.auth_service import create_token


def test_block_analysis_requires_login(client):
    response = client.post("/api/ai/block-analyses", json={"page_route": "/topics/stocks", "block_id": 1})
    assert response.status_code == 401


def test_block_analysis_api_returns_cache_for_logged_in_user(client):
    session = next(client.app.dependency_overrides[get_session]())
    user, block = _seed_user_model_block(session)
    cached = AIBlockAnalysis(
        page_route="/topics/stocks",
        block_id=block.id,
        block_title=block.title,
        source_type=block.source_type,
        data_hash="manual-cache",
        status="generated",
        summary_points_json=["缓存"],
        expires_at=datetime.utcnow() + timedelta(minutes=30),
        generated_by_user_id=user.id,
    )
    session.add(cached)
    session.commit()
    token = create_token(user)

    response = client.get(
        "/api/ai/block-analyses",
        params={"page_route": "/topics/stocks", "block_id": block.id, "data_hash": "manual-cache"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["summary_points"] == ["缓存"]


def test_analyze_block_uses_topic_prompt_template(client):
    session = next(client.app.dependency_overrides[get_session]())
    user, block = _seed_user_model_block(session)
    block.page_route = "/topics/stocks"
    block.source_type = "eastmoney_capital_flow"
    session.add(
        AIPromptTemplate(
            topic_slug="stocks",
            content_class="rank",
            topic_context="关注资金集中度",
            extra_forbidden="不得建议加仓",
            enabled=True,
        )
    )
    session.commit()
    captured: dict = {}

    async def fake_post(payload):
        captured["system"] = payload["messages"][0]["content"]
        return {
            "choices": [{"message": {"content": "{\"summary_points\":[\"资金集中在少数方向\"],\"key_changes\":[],\"risk_points\":[],\"related_entities\":[],\"confidence\":0.8}"}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
        }

    analysis = analyze_block(
        session,
        user=user,
        page_route="/topics/stocks",
        block_id=block.id,
        post_json=fake_post,
        resolved_data=[{"id": 1, "title": "资金流", "summary": "主力资金净流入", "score": 88}],
    )

    assert analysis.status == "generated"
    assert "关注资金集中度" in captured["system"]
    assert "不得建议加仓" in captured["system"]
    assert "识别数值、排名、资金、涨跌幅、积分等异常项" in captured["system"]
