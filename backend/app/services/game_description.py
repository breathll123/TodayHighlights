# -*- coding: utf-8 -*-
import asyncio
import json
import logging
import re
import time
from html import unescape
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import CryptoService
from app.core.logging import format_duration, log_event
from app.models.entities import AITokenUsage, GameItem
from app.services.ai_client import AIClient
from app.services.ai_models import get_default_ai_model

logger = logging.getLogger("today_highlights.ai")

GAME_DESCRIPTION_TRANSLATE_SYSTEM_PROMPT = (
    "你是今日看点的游戏简介翻译助手。"
    "你的任务是把游戏简介翻译成自然、简洁、易懂的中文。"
    "保留游戏名、专有名词、玩法类型，不要补充外部事实，不要营销夸张。"
    "如果原文已经是中文，只做必要清理。"
    "只输出合法 JSON，不输出 Markdown，不输出额外解释。"
)

GAME_DESCRIPTION_TRANSLATE_USER_PROMPT = (
    "请翻译以下游戏简介。输出字段：results。"
    "results 是数组，每项包含 external_id 和 zh。"
    "zh 最多 120 个中文字符，保留核心玩法和题材。\n\n"
)


def has_chinese(text: str) -> bool:
    return any("一" <= ch <= "鿿" for ch in text)


def normalize_game_description(text: object, *, max_chars: int = 500) -> str:
    if not isinstance(text, str):
        return ""
    cleaned = re.sub(r"<[^>]+>", " ", text)
    cleaned = unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:max_chars]


def merge_steam_details_into_items(items: list[dict[str, Any]], details_by_appid: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    if not details_by_appid:
        return items
    for item in items:
        detail = details_by_appid.get(str(item.get("external_id")))
        if not detail:
            continue
        metadata = dict(item.get("metadata") or {})
        description = normalize_game_description(detail.get("short_description"))
        if description:
            metadata["description_original"] = description
            metadata["description_source"] = "steam_appdetails.short_description"
        if not item.get("cover_url"):
            item["cover_url"] = str(detail.get("header_image") or detail.get("capsule_image") or "").strip()
        item["metadata"] = metadata
    return items


def ensure_description_original(metadata: dict[str, Any]) -> dict[str, Any]:
    next_metadata = dict(metadata or {})
    description = normalize_game_description(next_metadata.get("description_original"))
    if not description:
        description = normalize_game_description(next_metadata.get("short_description"))
    if not description:
        description = normalize_game_description(next_metadata.get("comments"))
        if description:
            next_metadata.setdefault("description_source", "wegame.comments")
    if description:
        next_metadata["description_original"] = description
    return next_metadata


def _chunked(items: list[GameItem], size: int) -> list[list[GameItem]]:
    return [items[index:index + size] for index in range(0, len(items), size)]


def _needs_translation(item: GameItem) -> bool:
    metadata = ensure_description_original(item.metadata_json or {})
    original = normalize_game_description(metadata.get("description_original"))
    if not original:
        return False
    zh = normalize_game_description(metadata.get("description_zh"), max_chars=180)
    return not zh


def translate_game_descriptions(session: Session, items: list[GameItem]) -> None:
    candidates = [item for item in items if _needs_translation(item)]
    if not candidates:
        return

    native: list[GameItem] = []
    pending: list[GameItem] = []
    for item in candidates:
        metadata = ensure_description_original(item.metadata_json or {})
        original = normalize_game_description(metadata.get("description_original"))
        if not original:
            continue
        if has_chinese(original):
            metadata["description_zh"] = original[:180]
            metadata["description_translated_by"] = "zh-native"
            item.metadata_json = metadata
            native.append(item)
        else:
            item.metadata_json = metadata
            pending.append(item)

    if native:
        log_event(
            logger,
            channel="application",
            category="ai",
            event="game.description.translate.native",
            size=len(native),
        )

    if not pending:
        return

    model_cfg = get_default_ai_model(session)
    if model_cfg is None:
        log_event(
            logger,
            channel="application",
            category="ai",
            event="game.description.translate.skipped",
            reason="no_default_ai_model",
            size=len(pending),
        )
        return

    crypto = CryptoService(settings.app_secret_key)
    client = AIClient(
        model_cfg.base_url,
        crypto.decrypt(model_cfg.api_key_encrypted),
        model_cfg.model,
        model_name=model_cfg.name,
        task_name="游戏简介翻译",
    )

    for index, batch in enumerate(_chunked(pending, 12), 1):
        started = time.perf_counter()
        payload = [
            {
                "external_id": item.external_id,
                "name": item.name,
                "provider": item.provider,
                "description": normalize_game_description((item.metadata_json or {}).get("description_original")),
            }
            for item in batch
        ]
        user_prompt = GAME_DESCRIPTION_TRANSLATE_USER_PROMPT + json.dumps(payload, ensure_ascii=False)
        try:
            result = asyncio.run(
                client.complete_json_with_usage(
                    GAME_DESCRIPTION_TRANSLATE_SYSTEM_PROMPT,
                    user_prompt,
                )
            )
        except Exception as exc:
            log_event(
                logger,
                channel="application",
                category="ai",
                event="game.description.translate.failed",
                level=logging.ERROR,
                error_type=type(exc).__name__,
                error=str(exc),
                batch=index,
                size=len(batch),
            )
            continue

        usage = AITokenUsage(
            user_id=None,
            model_config_id=model_cfg.id,
            model_name=model_cfg.model,
            usage_type="game_description",
            prompt_tokens=result.usage["prompt_tokens"],
            completion_tokens=result.usage["completion_tokens"],
            total_tokens=result.usage["total_tokens"],
            estimated=result.usage_estimated,
            request_status="success",
            prompt_text=f"{GAME_DESCRIPTION_TRANSLATE_SYSTEM_PROMPT}\n\n{user_prompt}",
            completion_text=result.content_text,
        )
        session.add(usage)

        zh_by_id = {
            str(row.get("external_id")): normalize_game_description(row.get("zh"), max_chars=180)
            for row in result.content.get("results", [])
            if isinstance(row, dict)
        }
        translated_count = 0
        for item in batch:
            zh = zh_by_id.get(item.external_id)
            if not zh:
                continue
            metadata = dict(item.metadata_json or {})
            metadata["description_zh"] = zh
            metadata["description_translated_by"] = model_cfg.model
            item.metadata_json = metadata
            translated_count += 1

        log_event(
            logger,
            channel="application",
            category="ai",
            event="game.description.translate.batch",
            model=model_cfg.model,
            batch=index,
            size=len(batch),
            translated=translated_count,
            duration=format_duration(time.perf_counter() - started),
        )
