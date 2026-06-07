import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx

from app.services.token_usage import extract_token_usage

PostJson = Callable[[dict], Awaitable[dict]]


@dataclass(frozen=True)
class AIJSONResult:
    content: dict
    content_text: str
    usage: dict
    usage_estimated: bool


class AIClient:
    def __init__(self, base_url: str, api_key: str, model: str, post_json: PostJson | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self._post_json = post_json

    async def complete_json(self, system_prompt: str, user_prompt: str) -> dict:
        result = await self.complete_json_with_usage(system_prompt, user_prompt)
        return result.content

    async def complete_json_with_usage(self, system_prompt: str, user_prompt: str) -> AIJSONResult:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        response = await self._send(payload)
        content_text = response["choices"][0]["message"]["content"]
        usage = extract_token_usage(response, f"{system_prompt}\n{user_prompt}", content_text)
        return AIJSONResult(
            content=json.loads(content_text),
            content_text=content_text,
            usage={
                "prompt_tokens": usage["prompt_tokens"],
                "completion_tokens": usage["completion_tokens"],
                "total_tokens": usage["total_tokens"],
            },
            usage_estimated=usage["estimated"],
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
