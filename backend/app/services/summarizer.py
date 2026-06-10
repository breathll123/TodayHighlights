import json
from dataclasses import dataclass
from typing import Awaitable, Callable

import httpx


@dataclass(frozen=True)
class HighlightDraft:
    title: str
    summary: str
    related_symbols: list[str]
    tags: list[str]
    score: int


PostJson = Callable[[dict], Awaitable[dict]]


class SummarizerClient:
    def __init__(self, base_url: str, api_key: str, model: str, post_json: PostJson | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self._post_json = post_json

    async def summarize(self, title: str, body: str) -> HighlightDraft:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "你是股票信息摘要助手，只输出 JSON。"},
                {
                    "role": "user",
                    "content": (
                        "基于以下雪球内容生成今日看点。输出字段：title, summary, "
                        "related_symbols, tags, score。"
                        f"\n标题：{title}\n正文：{body}"
                    ),
                },
            ],
            "temperature": 0.2,
        }
        response = await self._send(payload)
        content = response["choices"][0]["message"]["content"]
        data = json.loads(content)
        return HighlightDraft(
            title=str(data["title"]),
            summary=str(data["summary"]),
            related_symbols=[str(item) for item in data.get("related_symbols", [])],
            tags=[str(item) for item in data.get("tags", [])],
            score=int(data.get("score", 0)),
        )

    async def _send(self, payload: dict) -> dict:
        if self._post_json is not None:
            return await self._post_json(payload)
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            response.raise_for_status()
            return response.json()
