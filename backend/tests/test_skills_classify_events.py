# -*- coding: utf-8 -*-
import asyncio
import logging
from datetime import datetime

from app.services.skills.classify import classify_skills, translate_skills
from app.models.entities import Skill


class _FakeClient:
    """
    一个模拟的 AI 客户端，用于拦截 LLM 调用并直接返回硬编码的 JSON 分类和翻译结果。
    """
    model_name = "fake-model"

    async def complete_json(self, prompt: str, content: str) -> dict:
        import json
        items = json.loads(content)
        return {
            "results": [
                {
                    "full_name": i["full_name"],
                    "label": "skill",
                    "reason": "ok",
                    "zh": "中文描述"
                }
                for i in items
            ]
        }


def _skill(name: str) -> Skill:
    """
    辅助函数，创建一个临时测试用的 Skill 实体。
    """
    return Skill(
        source="github",
        external_id=name,
        name=name,
        url="u",
        description="An English skill description",
        extra_json={"full_name": name}
    )


def test_classify_emits_batch_event(caplog):
    """
    测试 classify_skills 在处理完一批技能后，是否会成功触发 skills.classify.batch 事件，
    并能够正确反向判断/标定实体为 skill。
    """
    skills = [_skill("a"), _skill("b")]
    with caplog.at_level(logging.INFO, logger="today_highlights.skills"):
        asyncio.run(classify_skills(_FakeClient(), skills, "p", "v1", batch_size=10,
                                    now=datetime(2026, 6, 25)))
    events = [getattr(r, "event", None) for r in caplog.records]
    assert "skills.classify.batch" in events
    assert all(s.is_skill for s in skills)


def test_translate_emits_batch_event(caplog):
    """
    测试 translate_skills 在翻译完一批技能后，是否会触发 skills.translate.batch 事件，
    且能够正确解析并更新实体的中文描述字段。
    """
    skills = [_skill("a")]
    skills[0].is_skill = True
    with caplog.at_level(logging.INFO, logger="today_highlights.skills"):
        asyncio.run(translate_skills(_FakeClient(), skills, "p", batch_size=10,
                                     now=datetime(2026, 6, 25)))
    events = [getattr(r, "event", None) for r in caplog.records]
    assert "skills.translate.batch" in events
    assert skills[0].description_zh == "中文描述"
