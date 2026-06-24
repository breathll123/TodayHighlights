"""LLM classification + translation over generic Skill rows (provider-agnostic).

Keyed by each skill's `full_name` (a unique, descriptive id the model echoes
back): for github that is `owner/repo`, stored in `extra_json["full_name"]`.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

from app.core.logging import log_event
from app.models.entities import Skill
from app.services.ai_client import AIClient

logger = logging.getLogger("today_highlights.skills")

_VALID_LABELS = {"skill", "collection", "tool_or_app", "unrelated"}


def has_chinese(text: str) -> bool:
    return any("一" <= ch <= "鿿" for ch in text)


def _chunked(items: list, size: int) -> list[list]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def skill_key(skill: Skill) -> str:
    """Unique, descriptive id passed to / echoed by the model."""
    return (skill.extra_json or {}).get("full_name") or skill.name or f"{skill.source}/{skill.external_id}"


async def classify_skills(
    client: AIClient, skills: list[Skill], prompt: str, prompt_version: str, batch_size: int, now: datetime,
) -> None:
    model = client.model_name
    for batch in _chunked(skills, batch_size):
        payload = [
            {"full_name": skill_key(s), "description": s.description, "topics": (s.extra_json or {}).get("topics", [])}
            for s in batch
        ]
        try:
            result = await client.complete_json(prompt, json.dumps(payload, ensure_ascii=False))
        except Exception as exc:  # noqa: BLE001 — log + skip batch, keep syncing
            log_event(logger, channel="application", category="ai", event="skills.classify.failed",
                      level=logging.ERROR, error_type=type(exc).__name__, error=str(exc), batch_size=len(batch))
            continue
        verdicts = {v.get("full_name"): v for v in result.get("results", [])}
        for s in batch:
            v = verdicts.get(skill_key(s))
            if not v:
                continue
            label = v.get("label") if v.get("label") in _VALID_LABELS else "unrelated"
            s.skill_kind = label
            s.is_skill = label == "skill"
            s.classify_reason = (v.get("reason") or "")[:120]
            s.classify_prompt_version = prompt_version
            s.classified_by_model = model
            s.classified_at = now


async def translate_skills(
    client: AIClient, skills: list[Skill], prompt: str, batch_size: int, now: datetime,
) -> None:
    model = client.model_name
    todo = [s for s in skills if s.is_skill and (not s.description_zh or not s.description_zh.strip())]
    pending: list[Skill] = []
    for s in todo:
        if not s.description:
            s.description_zh = ""
        elif has_chinese(s.description):
            s.description_zh = s.description
            s.translated_by_model = "zh-native"
            s.translated_at = now
        else:
            pending.append(s)

    for batch in _chunked(pending, batch_size):
        payload = [{"full_name": skill_key(s), "description": s.description} for s in batch]
        try:
            result = await client.complete_json(prompt, json.dumps(payload, ensure_ascii=False))
        except Exception as exc:  # noqa: BLE001
            log_event(logger, channel="application", category="ai", event="skills.translate.failed",
                      level=logging.ERROR, error_type=type(exc).__name__, error=str(exc), batch_size=len(batch))
            continue
        zh_by_key = {v.get("full_name"): (v.get("zh") or "").strip() for v in result.get("results", [])}
        for s in batch:
            zh = zh_by_key.get(skill_key(s))
            if zh:
                s.description_zh = zh
                s.translated_by_model = model
                s.translated_at = now
