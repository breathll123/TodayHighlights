import logging

from app.core.logging import bind_log_context
from app.models.entities import PageBlock
from app.services.blocks import get_page_blocks


def test_live_block_failure_keeps_request_context(client, monkeypatch, caplog):
    from app.core.database import get_session

    session = next(client.app.dependency_overrides[get_session]())
    block = PageBlock(
        page_route="/topics/test",
        title="测试区块",
        source_type="test_live",
        source_config={},
        display_count=5,
        enabled=True,
        status="published",
    )
    session.add(block)
    session.commit()
    caplog.set_level(logging.INFO)

    def fail_resolve(*_args, **_kwargs):
        raise RuntimeError("upstream unavailable")

    monkeypatch.setattr("app.services.blocks.resolve_block_data", fail_resolve)

    with bind_log_context(request_id="request-block-1234"):
        result = get_page_blocks(session, "/topics/test")

    assert result[0]["data"] == []
    record = next(
        record
        for record in caplog.records
        if getattr(record, "event", "") == "block_resolve_failed"
    )
    assert record.event_fields["request_id"] == "request-block-1234"
    assert record.event_fields["block_id"] == block.id
    assert record.event_fields["block_title"] == "测试区块"
    assert record.event_fields["page_route"] == "/topics/test"
    assert record.event_fields["source_type"] == "test_live"
    assert record.event_fields["reason"] == "exception"
