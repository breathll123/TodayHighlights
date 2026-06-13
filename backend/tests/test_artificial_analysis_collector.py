import gzip
import json
import logging

import httpx
import pytest
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.main import app
from app.models.entities import AASyncRun
from app.services.artificial_analysis.collector import (ArtificialAnalysisCollector, QuotaReserveReached,
                                                           ResponseTooLarge,
                                                           UpstreamRateLimited)
from app.services.artificial_analysis.constants import DATASETS


@pytest.fixture
def session(client) -> Session:
    return next(app.dependency_overrides[get_session]())


def _handler_for_payload(payload: dict, remaining: str = "24"):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            headers={
                "X-AA-Tier": "free",
                "X-RateLimit-Limit": "25",
                "X-RateLimit-Remaining": remaining,
                "X-RateLimit-Reset": "1781203200",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    return handler


def _client_factory(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def _make_run(session) -> AASyncRun:
    run = AASyncRun(trigger_type="manual", status="pending")
    session.add(run)
    session.flush()
    return run


def test_collect_language_follows_has_more_and_persists_each_page_before_decode(session, caplog):
    caplog.set_level(logging.INFO)
    page_1 = {
        "tier": "free",
        "intelligence_index_version": 4,
        "pagination": {"page": 1, "page_size": 1, "total_pages": 2, "has_more": True},
        "data": [{"id": "m1", "name": "Model 1"}],
    }
    page_2 = {
        "tier": "free",
        "intelligence_index_version": 4,
        "pagination": {"page": 2, "page_size": 1, "total_pages": 2, "has_more": False},
        "data": [{"id": "m2", "name": "Model 2"}],
    }
    pages = iter([page_1, page_2])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, json=next(pages),
                              headers={"X-AA-Tier": "free", "X-RateLimit-Remaining": "24",
                                       "Content-Type": "application/json"})

    client_factory = lambda: httpx.Client(transport=httpx.MockTransport(handler))
    run = _make_run(session)
    collector = ArtificialAnalysisCollector(session, client_factory=client_factory)
    result = collector.collect(run, DATASETS["language_global"])
    assert len(result.snapshot_ids) == 2
    assert len(result.payloads) == 2
    events = [
        record
        for record in caplog.records
        if getattr(record, "event", "") == "aa_page_collected"
    ]
    assert [record.event_fields["page"] for record in events] == [1, 2]
    assert all(record.event_fields["dataset_key"] == "language_global" for record in events)
    assert all(record.event_fields["ai_job_id"] == run.id for record in events)
    assert all(record.event_fields["response_bytes"] > 0 for record in events)


def test_collect_saves_only_allowlisted_headers(session):
    payload = {"tier": "free", "data": [{"id": "x", "name": "X"}]}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, json=payload,
                              headers={"X-AA-Tier": "free", "X-Secret": "leaked",
                                       "Content-Type": "application/json"})

    client_factory = lambda: httpx.Client(transport=httpx.MockTransport(handler))
    run = _make_run(session)
    collector = ArtificialAnalysisCollector(session, client_factory=client_factory)
    result = collector.collect(run, DATASETS["text_to_image"])
    assert len(result.snapshot_ids) == 1
    from app.models.entities import AARawSnapshot
    snapshot = session.query(AARawSnapshot).first()
    hdrs = snapshot.response_headers_json
    assert "x-secret" not in hdrs
    assert hdrs["x-aa-tier"] == "free"


def test_collect_stops_before_next_request_at_quota_reserve(session):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request,
                              json={"tier": "free", "data": [{"id": "a", "name": "A"}]},
                              headers={"X-RateLimit-Remaining": "1", "Content-Type": "application/json"})

    client_factory = lambda: httpx.Client(transport=httpx.MockTransport(handler))
    run = _make_run(session)
    run.quota_remaining = 2  # > reserve → proceeds, then handler returns 1 → next check stops
    session.flush()
    collector = ArtificialAnalysisCollector(session, client_factory=client_factory)
    result = collector.collect(run, DATASETS["text_to_image"])
    assert len(result.snapshot_ids) == 1  # first request succeeded, would stop before second


def test_collect_handles_429(session, caplog):
    caplog.set_level(logging.INFO)
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, request=request,
                              headers={"Retry-After": "60", "Content-Type": "application/json"})

    client_factory = lambda: httpx.Client(transport=httpx.MockTransport(handler))
    run = _make_run(session)
    collector = ArtificialAnalysisCollector(session, client_factory=client_factory)
    with pytest.raises(UpstreamRateLimited) as exc:
        collector.collect(run, DATASETS["text_to_image"])
    assert exc.value.retry_after_seconds == 60
    failed = [
        record
        for record in caplog.records
        if getattr(record, "event", "") == "aa_request_failed"
    ]
    assert len(failed) == 1
    assert failed[0].event_fields["stage"] == "rate_limit"
    assert failed[0].event_fields["dataset_key"] == "text_to_image"
    assert "x-api-key" not in str(failed[0].event_fields).lower()


def test_collect_rejects_body_over_limit(session, monkeypatch):
    monkeypatch.setattr("app.services.artificial_analysis.collector.settings.artificial_analysis_max_response_bytes", 10)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, content=b"x" * 100,
                              headers={"Content-Type": "application/json", "Content-Length": "100"})

    client_factory = lambda: httpx.Client(transport=httpx.MockTransport(handler))
    run = _make_run(session)
    collector = ArtificialAnalysisCollector(session, client_factory=client_factory)
    with pytest.raises(ResponseTooLarge):
        collector.collect(run, DATASETS["text_to_image"])


def test_api_key_is_sent_but_never_persisted(session):
    captured_key = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_key
        captured_key = request.headers.get("x-api-key")
        return httpx.Response(200, request=request,
                              json={"tier": "free", "data": [{"id": "x", "name": "X"}]},
                              headers={"Content-Type": "application/json"})

    client_factory = lambda: httpx.Client(transport=httpx.MockTransport(handler))
    run = _make_run(session)
    collector = ArtificialAnalysisCollector(session, client_factory=client_factory)
    collector.collect(run, DATASETS["text_to_image"])
    assert captured_key is not None
    from app.services.artificial_analysis.collector import SAFE_HEADERS
    assert "x-api-key" not in SAFE_HEADERS

    from app.models.entities import AARawSnapshot
    snapshots = session.query(AARawSnapshot).all()
    for snap in snapshots:
        assert "x-api-key" not in str(snap.response_headers_json).lower()
