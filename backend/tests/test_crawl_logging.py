import logging
from datetime import datetime

from app.core.database import get_session
from app.models.entities import Source, Topic
from app.services.jobs import run_crawl_job
from app.sources.base import RawItemDraft


class _Crypto:
    def __init__(self, _key: str):
        pass

    def decrypt(self, _value: str) -> str:
        return ""


class _SuccessfulAdapter:
    def fetch(self, _entry_url: str, _cookie: str) -> list[RawItemDraft]:
        return [
            RawItemDraft(
                external_id="item-1",
                url="https://example.com/item-1",
                author="测试来源",
                title="测试公告",
                body="正文",
                published_at=datetime.utcnow(),
                content_hash="hash-1",
            )
        ]


class _FailingAdapter:
    def fetch(self, _entry_url: str, _cookie: str) -> list[RawItemDraft]:
        raise RuntimeError("upstream unavailable")


def _source(client) -> tuple[object, Topic, Source]:
    session = next(client.app.dependency_overrides[get_session]())
    topic = Topic(name="股票", slug="stocks", enabled=True)
    session.add(topic)
    session.flush()
    source = Source(
        topic_id=topic.id,
        site="test",
        name="指数行情",
        entry_url="https://example.com",
        enabled=True,
        cookie_encrypted="",
        enable_highlight=False,
    )
    session.add(source)
    session.commit()
    return session, topic, source


def test_crawl_completion_contains_names_counts_and_ids(client, monkeypatch, caplog):
    session, topic, source = _source(client)
    monkeypatch.setattr("app.services.jobs.CryptoService", _Crypto)
    monkeypatch.setattr("app.services.jobs.get_adapter", lambda _site: _SuccessfulAdapter())
    caplog.set_level(logging.INFO)

    job = run_crawl_job(session, source.id, "manual")

    record = next(r for r in caplog.records if getattr(r, "event", "") == "crawl.completed")
    assert record.event_fields["source_name"] == "指数行情"
    assert record.event_fields["topic_name"] == "股票"
    assert record.event_fields["source_id"] == source.id
    assert record.event_fields["job_id"] == job.id
    assert record.event_fields["found"] == 1
    assert record.event_fields["saved"] == 1


def test_crawl_failure_keeps_readable_context(client, monkeypatch, caplog):
    session, topic, source = _source(client)
    monkeypatch.setattr("app.services.jobs.CryptoService", _Crypto)
    monkeypatch.setattr("app.services.jobs.get_adapter", lambda _site: _FailingAdapter())
    caplog.set_level(logging.INFO)

    job = run_crawl_job(session, source.id, "scheduled")

    record = next(r for r in caplog.records if getattr(r, "event", "") == "crawl.failed")
    assert job.status == "failed"
    assert record.event_fields["source_name"] == "指数行情"
    assert record.event_fields["topic_name"] == "股票"
    assert record.event_fields["stage"] == "fetch"
    assert record.event_fields["error_type"] == "RuntimeError"
    assert record.event_fields["error"] == "upstream unavailable"
    assert record.event_fields["job_id"] == job.id
