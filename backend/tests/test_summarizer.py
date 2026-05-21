import pytest

from app.services.summarizer import HighlightDraft, SummarizerClient


@pytest.mark.asyncio
async def test_summarizer_parses_json_response() -> None:
    async def fake_post(payload: dict) -> dict:
        return {
            "choices": [
                {
                    "message": {
                        "content": "{\"title\":\"资金关注新能源\",\"summary\":\"新能源板块热度上升。\",\"related_symbols\":[\"新能源\"],\"tags\":[\"资金\"],\"score\":82}"
                    }
                }
            ]
        }

    client = SummarizerClient("https://api.example.com/v1", "key", "model", post_json=fake_post)
    result = await client.summarize("标题", "正文")

    assert result == HighlightDraft(
        title="资金关注新能源",
        summary="新能源板块热度上升。",
        related_symbols=["新能源"],
        tags=["资金"],
        score=82,
    )
