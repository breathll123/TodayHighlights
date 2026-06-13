import logging
from types import SimpleNamespace

from apscheduler.events import (
    EVENT_JOB_ERROR,
    EVENT_JOB_EXECUTED,
    EVENT_JOB_MAX_INSTANCES,
    EVENT_JOB_MISSED,
)

from app.core.scheduler import _handle_scheduler_event
from app.services.artificial_analysis.sync import scheduled_sync


def test_scheduler_listener_emits_structured_events(caplog):
    caplog.set_level(logging.INFO)

    _handle_scheduler_event(SimpleNamespace(code=EVENT_JOB_EXECUTED, job_id="success"))
    _handle_scheduler_event(
        SimpleNamespace(code=EVENT_JOB_ERROR, job_id="failure", exception=RuntimeError("boom"))
    )
    _handle_scheduler_event(SimpleNamespace(code=EVENT_JOB_MISSED, job_id="missed"))
    _handle_scheduler_event(SimpleNamespace(code=EVENT_JOB_MAX_INSTANCES, job_id="busy"))

    events = {getattr(record, "event", ""): record for record in caplog.records}
    assert events["scheduled_job_finished"].event_fields["job_id"] == "success"
    assert events["scheduled_job_failed"].event_fields["exception_type"] == "RuntimeError"
    assert events["scheduled_job_missed"].event_fields["job_id"] == "missed"
    assert events["scheduled_job_skipped"].event_fields["reason"] == "max_instances"


def test_scheduled_aa_sync_logs_missing_api_key_skip(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    monkeypatch.setattr(
        "app.services.artificial_analysis.sync.settings.artificial_analysis_sync_enabled",
        True,
    )
    monkeypatch.setattr(
        "app.services.artificial_analysis.sync.settings.artificial_analysis_api_key",
        "",
    )

    scheduled_sync()

    record = next(
        record
        for record in caplog.records
        if getattr(record, "event", "") == "aa_sync_skipped"
    )
    assert record.event_fields["reason"] == "missing_api_key"
    assert record.event_fields["trigger_type"] == "scheduled"
