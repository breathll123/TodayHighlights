import logging
from queue import Queue

from app.core.logging import SafeQueueHandler, StructuredTextFormatter, build_event_record
from app.core.logging_catalog import EVENT_SPECS, event_spec


def test_event_catalog_contains_canonical_and_legacy_events():
    canonical = {
        "app.started",
        "app.stopping",
        "http.completed",
        "http.unhandled",
        "crawl.started",
        "crawl.fetch.completed",
        "crawl.persist.completed",
        "crawl.completed",
        "crawl.failed",
        "upstream.completed",
        "upstream.failed",
        "ai.request.completed",
        "ai.request.failed",
        "ai.enrichment.completed",
        "ai.block.completed",
        "scheduler.job.completed",
        "scheduler.job.failed",
        "admin.changed",
    }
    legacy = {
        "application_started",
        "http_request_completed",
        "crawl_job_finished",
        "external_request_failed",
        "ai_request_finished",
        "scheduled_job_failed",
        "media_cache_failed",
        "aa_sync_finished",
    }

    assert canonical | legacy <= EVENT_SPECS.keys()
    assert event_spec("app.started").description != "业务事件"


def test_unknown_event_uses_business_event_fallback():
    spec = event_spec("custom.integration.notice")

    assert spec.description == "业务事件"
    assert spec.field_order == ()
    assert spec.expanded_fields == ()


def test_formatter_prioritizes_names_and_results_before_ids():
    formatter = StructuredTextFormatter()
    record = build_event_record(
        logging.INFO,
        channel="application",
        category="crawler",
        event="crawl.completed",
        source_id=7,
        request_id="req-12345678",
        duration_ms=18.5,
        status="success",
        source_name="晨间资讯",
        items_saved=6,
    )

    lines = formatter.format(record).splitlines()

    assert len(lines) == 2
    assert "INFO     crawler      crawl.completed 抓取任务完成" in lines[0]
    assert lines[1].index("source_name=") < lines[1].index("status=")
    assert lines[1].index("status=") < lines[1].index("source_id=")
    assert lines[1].index("items_saved=") < lines[1].index("request_id=")


def test_formatter_keeps_unlisted_fields_in_insertion_order():
    formatter = StructuredTextFormatter()
    record = build_event_record(
        logging.INFO,
        channel="application",
        event="custom.integration.notice",
        zebra=1,
        alpha=2,
    )

    details = formatter.format(record).splitlines()[1]

    assert details.index("zebra=1") < details.index("alpha=2")


def test_failure_url_and_response_preview_are_expanded_and_redacted():
    formatter = StructuredTextFormatter()
    record = build_event_record(
        logging.ERROR,
        channel="application",
        category="upstream",
        event="upstream.failed",
        provider="example",
        status=502,
        url="https://example.test/data?token=secret-value",
        response_preview="authorization=Bearer private-value\nbad gateway",
    )

    lines = formatter.format(record).splitlines()

    assert len(lines) == 4
    assert "provider=example status=502" in lines[1]
    assert lines[2].startswith("  url=")
    assert lines[3].startswith("  response_preview=")
    assert "secret-value" not in lines[2]
    assert "private-value" not in lines[3]
    assert "\\nbad gateway" in lines[3]


def test_queue_prepare_resolves_third_party_message_placeholders():
    handler = SafeQueueHandler(Queue())
    record = logging.LogRecord(
        "third.party",
        logging.INFO,
        "",
        0,
        "Cleanup deleted %d rows from %s",
        (3, "cache"),
        None,
    )

    prepared = handler.prepare(record)
    text = StructuredTextFormatter().format(prepared)

    assert "Cleanup deleted 3 rows from cache" in text
    assert "%d" not in text
    assert prepared.args is None
