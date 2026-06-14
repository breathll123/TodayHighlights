import json
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from app.core.logging import format_duration, log_event
from app.services.token_usage import extract_token_usage

logger = logging.getLogger("today_highlights.ai")
PostJson = Callable[[dict], Awaitable[dict]]


@dataclass(frozen=True)
class AIJSONResult:
    content: dict
    content_text: str
    usage: dict
    usage_estimated: bool


class AIClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        post_json: PostJson | None = None,
        *,
        model_name: str | None = None,
        task_name: str = "内容分析",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.model_name = model_name or model
        self.task_name = task_name
        self._post_json = post_json
        self._host = urlparse(base_url).hostname or "unknown"

    async def complete_json(self, system_prompt: str, user_prompt: str) -> dict:
        result = await self.complete_json_with_usage(system_prompt, user_prompt)
        return result.content

    async def complete_json_with_usage(self, system_prompt: str, user_prompt: str) -> AIJSONResult:
        started = time.perf_counter()
        stage = "transport"
        input_chars = len(system_prompt) + len(user_prompt)
        log_event(
            logger,
            channel="application",
            category="ai",
            event="ai.request.started",
            model_name=self.model_name,
            task_name=self.task_name,
            input_chars=input_chars,
            host=self._host,
        )

        try:
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

            stage = "decode"
            parsed = json.loads(content_text)
            usage = extract_token_usage(response, f"{system_prompt}\n{user_prompt}", content_text)

            log_event(
                logger,
                channel="application",
                category="ai",
                event="ai.request.completed",
                model_name=self.model_name,
                task_name=self.task_name,
                host=self._host,
                input_chars=input_chars,
                output_chars=len(content_text),
                output_keys=sorted(parsed.keys()),
                tokens={
                    "prompt": usage["prompt_tokens"],
                    "completion": usage["completion_tokens"],
                    "total": usage["total_tokens"],
                    "estimated": usage["estimated"],
                },
                duration=format_duration(time.perf_counter() - started),
            )

            return AIJSONResult(
                content=parsed,
                content_text=content_text,
                usage={
                    "prompt_tokens": usage["prompt_tokens"],
                    "completion_tokens": usage["completion_tokens"],
                    "total_tokens": usage["total_tokens"],
                },
                usage_estimated=usage["estimated"],
            )

        except json.JSONDecodeError as exc:
            log_event(
                logger,
                channel="application",
                category="ai",
                event="ai.request.failed",
                level=logging.ERROR,
                model_name=self.model_name,
                task_name=self.task_name,
                stage=stage,
                error_type=type(exc).__name__,
                error=str(exc),
                duration=format_duration(time.perf_counter() - started),
            )
            raise
        except Exception as exc:
            log_event(
                logger,
                channel="application",
                category="ai",
                event="ai.request.failed",
                level=logging.ERROR,
                model_name=self.model_name,
                task_name=self.task_name,
                stage=stage,
                error_type=type(exc).__name__,
                error=str(exc),
                duration=format_duration(time.perf_counter() - started),
            )
            raise

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
