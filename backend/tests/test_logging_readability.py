import ast
import logging
from pathlib import Path
from queue import Queue

from app.core.logging import SafeQueueHandler, StructuredTextFormatter, build_event_record
from app.core.logging_catalog import EVENT_SPECS, EventSpec, event_spec


def test_event_catalog_contains_canonical_events():
    canonical = {
        "aa.sync.completed",
        "adapter.failed",
        "admin.changed",
        "ai.block.completed",
        "ai.enrichment.completed",
        "ai.request.completed",
        "app.started",
        "app.stopping",
        "block.resolve.failed",
        "cache.backend.ready",
        "crawl.completed",
        "crawl.failed",
        "crawl.fetch.completed",
        "crawl.persist.completed",
        "crawl.started",
        "http.completed",
        "http.unhandled",
        "media.cache.failed",
        "scheduler.job.completed",
        "scheduler.job.failed",
        "upstream.completed",
        "upstream.failed",
    }

    assert canonical <= EVENT_SPECS.keys()
    assert event_spec("app.started").description != "业务事件"


def test_all_literal_application_events_are_registered():
    app_root = Path(__file__).parents[1] / "app"
    emitted: set[str] = set()
    for path in app_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                if (
                    keyword.arg == "event"
                    and isinstance(keyword.value, ast.Constant)
                    and isinstance(keyword.value.value, str)
                ):
                    emitted.add(keyword.value.value)

    assert emitted <= EVENT_SPECS.keys()


def test_unknown_event_uses_business_event_fallback():
    spec = event_spec("custom.integration.notice")

    assert spec.description == "业务事件"
    assert spec.field_order == ()
    assert spec.expanded_fields == ()


def test_legacy_context_and_result_fields_precede_ids_in_catalog():
    field_order = event_spec("aa.page.collected").field_order
    readable_fields = {
        "endpoint",
        "backend",
        "query_keys",
        "client_ip",
        "url_hash",
        "retry_after_seconds",
        "dataset_count",
        "snapshot_count",
    }
    id_fields = {
        "source_id",
        "crawl_job_id",
        "ai_job_id",
        "job_id",
        "dataset_id",
        "snapshot_id",
        "enrichment_id",
        "block_id",
        "user_id",
        "request_id",
    }

    first_id = min(field_order.index(field) for field in id_fields)

    assert readable_fields <= set(field_order)
    assert all(field_order.index(field) < first_id for field in readable_fields)


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


def test_aa_result_counts_are_rendered_before_ids():
    formatter = StructuredTextFormatter()
    record = build_event_record(
        logging.INFO,
        channel="application",
        category="ai",
        event="aa.dataset.completed",
        dataset_id=17,
        entry_count=8,
        snapshot_count=3,
    )

    details = formatter.format(record).splitlines()[1]

    assert details.index("entry_count=8") < details.index("dataset_id=17")
    assert details.index("snapshot_count=3") < details.index("dataset_id=17")


def test_aa_requested_dataset_count_is_rendered_before_ids():
    formatter = StructuredTextFormatter()
    record = build_event_record(
        logging.INFO,
        channel="application",
        category="ai",
        event="aa.sync.requested",
        ai_job_id=23,
        user_id=5,
        dataset_count=4,
    )

    details = formatter.format(record).splitlines()[1]

    assert details.index("dataset_count=4") < details.index("ai_job_id=23")
    assert details.index("dataset_count=4") < details.index("user_id=5")


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


def test_upstream_failure_details_are_expanded_and_redacted():
    formatter = StructuredTextFormatter()
    record = build_event_record(
        logging.ERROR,
        channel="application",
        category="upstream",
        event="upstream.failed",
        provider="example",
        status=502,
        url="https://example.test/data?token=secret-value",
        request_headers={"user-agent": "DataFlow", "referer": "token=referer-secret"},
        response_preview="authorization=Bearer private-value\nbad gateway",
    )

    lines = formatter.format(record).splitlines()

    assert len(lines) == 5
    assert "provider=example status=502" in lines[1]
    assert lines[2].startswith("  url=")
    assert lines[3].startswith("  request_headers=")
    assert lines[4].startswith("  response_preview=")
    assert "secret-value" not in lines[2]
    assert "referer-secret" not in lines[3]
    assert "private-value" not in lines[4]
    assert "\\nbad gateway" in lines[4]


def test_upstream_success_url_is_expanded():
    formatter = StructuredTextFormatter()
    record = build_event_record(
        logging.INFO,
        channel="application",
        category="crawler",
        event="upstream.completed",
        provider="example",
        status=200,
        url="https://example.test/data?page=2",
    )

    lines = formatter.format(record).splitlines()

    assert len(lines) == 3
    assert "provider=example status=200" in lines[1]
    assert lines[2] == "  url=https://example.test/data?page=2"


def test_canonical_categories_share_event_column_without_truncation():
    formatter = StructuredTextFormatter()
    categories = ("ai", "block", "cache", "crawler", "media", "scheduler", "application")
    lines = []
    for category in categories:
        record = build_event_record(
            logging.INFO,
            channel="application",
            category=category,
            event="crawl.completed",
        )
        lines.append(formatter.format(record).splitlines()[0])

    event_columns = {line.index("crawl.completed") for line in lines}

    assert len(event_columns) == 1
    assert any("application" in line for line in lines)
    assert any("scheduler" in line for line in lines)


def test_unknown_long_category_is_preserved_and_expands_column():
    formatter = StructuredTextFormatter()
    record = build_event_record(
        logging.INFO,
        channel="application",
        category="artificial-analysis",
        event="crawl.completed",
    )

    line = formatter.format(record).splitlines()[0]

    assert "artificial-analysis crawl.completed" in line


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
    assert prepared.getMessage() == "Cleanup deleted 3 rows from cache"
    assert prepared.args is None


def test_queue_prepare_resolves_message_when_custom_event_exists():
    handler = SafeQueueHandler(Queue())
    record = logging.LogRecord(
        "third.party",
        logging.WARNING,
        "",
        0,
        "Retry %d failed for %s",
        (2, "upstream"),
        None,
    )
    record.event = "upstream.failed"

    prepared = handler.prepare(record)

    assert prepared.event == "upstream.failed"
    assert prepared.getMessage() == "Retry 2 failed for upstream"
    assert prepared.msg == "Retry 2 failed for upstream"
    assert prepared.args is None


def test_third_party_multiline_message_stays_in_single_headline(monkeypatch):
    handler = SafeQueueHandler(Queue())
    record = logging.LogRecord(
        "third.party",
        logging.INFO,
        "",
        0,
        "Cleanup\r\n\tdeleted %d rows",
        (3,),
        None,
    )
    record.category = "third\r\n\tparty"
    record.event_fields = {"attempt": 2}
    monkeypatch.setitem(
        EVENT_SPECS,
        "Cleanup\r\n\tdeleted 3 rows",
        EventSpec("第三方\r\n\t消息", ()),
    )

    prepared = handler.prepare(record)
    lines = StructuredTextFormatter().format(prepared).splitlines()

    assert len(lines) == 2
    assert "third party" in lines[0]
    assert "Cleanup deleted 3 rows 第三方 消息" in lines[0]
    assert lines[1] == "  attempt=2"
