import asyncio
import logging

import pytest

from app.services.ai_client import AIClient


def test_ai_client_logs_readable_usage_without_prompt_content(caplog):
    async def fake_post(_payload):
        return {
            "choices": [{"message": {"content": '{"summary":"ok"}'}}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
        }

    caplog.set_level(logging.INFO)
    client = AIClient(
        "https://example.com/v1",
        "api-secret",
        "model-a",
        post_json=fake_post,
        model_name="默认模型 / model-a",
        task_name="区块分析",
    )

    asyncio.run(
        client.complete_json_with_usage(
            "system prompt private-value",
            "user prompt private-value",
        )
    )

    record = next(
        record
        for record in caplog.records
        if getattr(record, "event", "") == "ai.request.completed"
    )
    assert record.event_fields["model_name"] == "默认模型 / model-a"
    assert record.event_fields["task_name"] == "区块分析"
    assert record.event_fields["input_chars"] > 0
    assert record.event_fields["output_chars"] > 0
    assert record.event_fields["tokens"] == {
        "prompt": 11,
        "completion": 7,
        "total": 18,
        "estimated": False,
    }
    rendered = repr(record.event_fields)
    assert "private-value" not in rendered
    assert "api-secret" not in rendered


def test_ai_client_failure_logs_task_context_without_prompt(caplog):
    async def fail(_payload):
        raise RuntimeError("provider unavailable")

    caplog.set_level(logging.INFO)
    client = AIClient(
        "https://example.com/v1",
        "api-secret",
        "model-a",
        post_json=fail,
        model_name="默认模型 / model-a",
        task_name="单条内容加工",
    )

    with pytest.raises(RuntimeError):
        asyncio.run(client.complete_json("system private-value", "user private-value"))

    record = next(
        record
        for record in caplog.records
        if getattr(record, "event", "") == "ai.request.failed"
    )
    assert record.event_fields["model_name"] == "默认模型 / model-a"
    assert record.event_fields["task_name"] == "单条内容加工"
    assert record.event_fields["stage"] == "transport"
    assert record.event_fields["error_type"] == "RuntimeError"
    assert "private-value" not in repr(record.event_fields)
