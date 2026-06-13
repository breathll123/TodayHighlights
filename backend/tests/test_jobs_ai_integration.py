from datetime import datetime

from app.core.config import settings
from app.core.crypto import CryptoService
from app.core.database import get_session
from app.models.entities import AIGenerationJob, AIItemEnrichment, AIModelConfig, Highlight, RawItem, Source, Topic
from app.services.ai_enrichment import create_pending_enrichments, process_item_enrichment, select_item_candidates

FAKE_ITEM_RESPONSE = {
    "choices": [
        {
            "message": {
                "content": '{"title":"资金关注新能源","summary":"新能源相关公告密集发布，市场关注度有所提升。","tags":["新能源","公告"],"related_symbols":["新能源"],"importance_score":72,"focus_points":["公告密集发布"],"risk_points":["短期波动仍需观察"]}'
            }
        }
    ]
}


async def _fake_post_json(_payload: dict) -> dict:
    return FAKE_ITEM_RESPONSE


async def _failing_post_json(_payload: dict) -> dict:
    raise RuntimeError("upstream unavailable")


def test_process_item_enrichment_creates_highlight_and_job(client) -> None:
    session = next(client.app.dependency_overrides[get_session]())

    # Set up stock topic + source
    topic = Topic(name="股票", slug="stocks", sort_order=1, enabled=True)
    session.add(topic)
    session.flush()

    source = Source(topic_id=topic.id, site="tonghuashun", name="同花顺", entry_url="https://example.com", enabled=True, enable_highlight=True)
    session.add(source)
    session.flush()

    # Set up default AI model config with properly encrypted API key
    crypto = CryptoService(settings.app_secret_key)
    model_cfg = AIModelConfig(
        name="Test Model",
        base_url="https://api.test.com/v1",
        model="test-model",
        api_key_encrypted=crypto.encrypt("test-api-key"),
        is_default=True,
        enabled=True,
    )
    session.add(model_cfg)
    session.flush()

    # Create a raw item
    raw = RawItem(
        source_id=source.id,
        external_id="test-1",
        url="https://example.com/1",
        title="新能源公告密集发布",
        body="新能源板块相关公司公告密集发布，市场关注度持续提升中，多家龙头企业披露重要信息。",
        published_at=datetime.utcnow(),
        metrics_json={},
        content_hash="test-hash-1",
    )
    session.add(raw)
    session.commit()

    # Select candidates and create pending enrichments
    candidates = select_item_candidates(session, source.topic_id, [raw], limit=50)
    assert len(candidates) == 1

    enrichments = create_pending_enrichments(session, source.topic_id, candidates)
    assert len(enrichments) == 1
    enrichment_id = enrichments[0].id

    # Process the enrichment with mocked AI
    enrichment = process_item_enrichment(session, enrichment_id, post_json=_fake_post_json, trigger_type="crawl")
    session.commit()

    # Assert enrichment state
    assert enrichment.status == "generated"
    assert enrichment.generated_title == "资金关注新能源"
    assert enrichment.importance_score == 72
    assert enrichment.tags_json == ["新能源", "公告"]
    assert enrichment.generated_by_model == "test-model"
    assert enrichment.generated_at is not None

    # Assert highlight was created
    highlight = session.query(Highlight).filter(Highlight.raw_item_id == raw.id).first()
    assert highlight is not None
    assert highlight.title == "资金关注新能源"
    assert highlight.topic_id == topic.id
    assert highlight.generated_by_model == "test-model"

    # Assert job was logged
    job = session.query(AIGenerationJob).filter(AIGenerationJob.item_enrichment_id == enrichment_id).first()
    assert job is not None
    assert job.status == "succeeded"
    assert job.job_type == "item_enrichment"
    assert job.trigger_type == "crawl"


def test_process_item_enrichment_failure_updates_existing_job(client) -> None:
    session = next(client.app.dependency_overrides[get_session]())
    topic = Topic(name="股票", slug="stocks", sort_order=1, enabled=True)
    session.add(topic)
    session.flush()
    source = Source(
        topic_id=topic.id,
        site="tonghuashun",
        name="同花顺",
        entry_url="https://example.com",
        enabled=True,
        enable_highlight=True,
    )
    session.add(source)
    session.flush()
    crypto = CryptoService(settings.app_secret_key)
    model_cfg = AIModelConfig(
        name="Test Model",
        base_url="https://api.test.com/v1",
        model="test-model",
        api_key_encrypted=crypto.encrypt("test-api-key"),
        is_default=True,
        enabled=True,
    )
    session.add(model_cfg)
    session.flush()
    raw = RawItem(
        source_id=source.id,
        external_id="test-failure",
        url="https://example.com/failure",
        title="测试失败",
        body="这是一条长度足够的测试正文，用于触发 AI 加工失败并验证任务状态不会永久停留在处理中。",
        published_at=datetime.utcnow(),
        metrics_json={},
        content_hash="test-failure-hash",
    )
    session.add(raw)
    session.commit()

    enrichment = create_pending_enrichments(session, topic.id, [raw])[0]
    result = process_item_enrichment(
        session,
        enrichment.id,
        post_json=_failing_post_json,
        trigger_type="crawl",
    )
    session.flush()

    jobs = (
        session.query(AIGenerationJob)
        .filter(AIGenerationJob.item_enrichment_id == enrichment.id)
        .all()
    )
    assert result.status == "failed"
    assert len(jobs) == 1
    assert jobs[0].status == "failed"
    assert jobs[0].finished_at is not None
