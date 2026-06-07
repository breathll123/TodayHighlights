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
