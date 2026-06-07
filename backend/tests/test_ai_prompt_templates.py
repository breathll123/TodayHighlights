from sqlalchemy import inspect, select

from app.core.database import get_session
from app.models.entities import AIPromptTemplate


def test_ai_prompt_templates_table_columns_exist(client):
    session = next(client.app.dependency_overrides[get_session]())
    columns = {col["name"] for col in inspect(session.bind).get_columns("ai_prompt_templates")}

    assert {
        "id",
        "topic_slug",
        "content_class",
        "topic_context",
        "extra_forbidden",
        "enabled",
        "template_version",
        "updated_by_user_id",
        "notes",
        "created_at",
        "updated_at",
    }.issubset(columns)


def test_ai_prompt_template_model_can_store_context(client):
    session = next(client.app.dependency_overrides[get_session]())
    template = AIPromptTemplate(
        topic_slug="stocks",
        content_class="news",
        topic_context="关注政策信号",
        extra_forbidden="不得给出买卖建议",
        enabled=True,
        notes="test",
    )
    session.add(template)
    session.commit()

    saved = session.scalar(select(AIPromptTemplate).where(AIPromptTemplate.topic_slug == "stocks"))
    assert saved is not None
    assert saved.content_class == "news"
    assert saved.template_version == 1


from app.services.ai_block_prompts import (
    build_block_system_prompt,
    get_content_class,
    infer_topic_slug,
)


def test_get_content_class_maps_existing_source_types():
    assert get_content_class("aihot_news") == "news"
    assert get_content_class("eastmoney_capital_flow") == "rank"
    assert get_content_class("qiumiwu_schedule") == "event"
    assert get_content_class("unknown_source") == "news"


def test_infer_topic_slug_from_routes():
    assert infer_topic_slug("/topics/stocks") == "stocks"
    assert infer_topic_slug("/topics/football") == "football"
    assert infer_topic_slug("/topics/ai") == "ai"
    assert infer_topic_slug("/") == "summary"


def test_build_block_system_prompt_injects_template_context():
    template = AIPromptTemplate(
        topic_slug="ai",
        content_class="news",
        topic_context="关注模型能力变化",
        extra_forbidden="不得编造机构名称",
        enabled=True,
    )

    prompt = build_block_system_prompt("ai", "news", template)

    assert "当前分析领域：ai" in prompt
    assert "【领域背景】" in prompt
    assert "关注模型能力变化" in prompt
    assert "不得编造机构名称" in prompt
    assert "summary_points" in prompt
    assert "只输出合法 JSON" in prompt


def test_build_block_system_prompt_without_template_uses_default_framework():
    prompt = build_block_system_prompt("football", "event", None)

    assert "当前分析领域：football" in prompt
    assert "提取关键事实、时间、状态和结果" in prompt
    assert "【领域背景】" not in prompt
