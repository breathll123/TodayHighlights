from sqlalchemy import inspect

from app.core.database import Base, get_session
from app.models.entities import AIGenerationJob, AIItemEnrichment, AIModelConfig, AITopicSummary


def test_ai_tables_are_registered() -> None:
    assert AIModelConfig.__tablename__ in Base.metadata.tables
    assert AIItemEnrichment.__tablename__ in Base.metadata.tables
    assert AITopicSummary.__tablename__ in Base.metadata.tables
    assert AIGenerationJob.__tablename__ in Base.metadata.tables


def test_ai_item_enrichment_retry_columns_exist(client) -> None:
    session = next(client.app.dependency_overrides[get_session]())
    columns = {col["name"] for col in inspect(session.bind).get_columns("ai_item_enrichments")}
    assert {"retry_count", "last_attempted_at", "error_message", "status"}.issubset(columns)


def test_ai_topic_summaries_version_column_exists(client) -> None:
    session = next(client.app.dependency_overrides[get_session]())
    columns = {col["name"] for col in inspect(session.bind).get_columns("ai_topic_summaries")}
    assert {"topic_id", "summary_date", "version", "items_json", "status"}.issubset(columns)
