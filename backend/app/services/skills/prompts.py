"""Skills classify/translate prompts — editable from the admin (Prompt 模板 page),
stored in app_settings, falling back to the code defaults below.

The classify prompt's hash (`classify_prompt_version`) is stamped onto every
classification; when the prompt changes the hash changes, so the next sync
re-classifies every affected row automatically.
"""
from __future__ import annotations

import hashlib

from app.services.settings import get_plain_setting, set_plain_setting

CLASSIFY_PROMPT_KEY = "skills.classify_prompt"
TRANSLATE_PROMPT_KEY = "skills.translate_prompt"

DEFAULT_CLASSIFY_PROMPT = """\
你在为「AI agent skill 及专属框架」排行榜做仓库筛选。把每个 GitHub 仓库分类，
只保留「单个可安装的 skill」和「开发/集成/运行 agent skills 的专属框架与SDK」。
一个 agent skill 是自包含、可安装的单一能力（通常是 SKILL.md + 可选脚本），由 AI 编码 agent 调用完成一件聚焦的事。
专门用于构建、运行或集成这类 agent skills 的专属开发框架与 SDK 也视为保留的 skill。
不是给人运行的普通 app，不是与 agent 无关的通用框架/SDK，不是多 skill 合集/清单/市场，也不是通用的 IDE。

标签（每个仓库恰好一个）：
- skill        ：单个可安装的 agent skill，或用于开发/运行 agent skills 的专属开发框架与 SDK。【保留】
- collection   ：多 skill 合集 / awesome 清单 / marketplace / 官方多 skill 仓库。【剔除】
- tool_or_app  ：普通应用/CLI/桌面端/IDE/平台，或与 agent skills 无关的通用开发框架/SDK。【剔除】
- unrelated    ：领域无关、纯蹭 topic。【剔除】

规则：
1. 仓库提供「单一聚焦能力」或作为专门开发/运行 agent skills 的专属框架与 SDK → skill；
2. 包含/链接多个 skill 或名字 awesome-* → collection；
3. 由人当普通应用运行或是与 agent 无关的通用框架 → tool_or_app；
4. 主题与 agent skill 完全无关 → unrelated；
5. 从严判定，拿不准时选择剔除标签并标低 confidence。
6. 只依据 name + description + topics 进行判断；若 description 为空，则按 name+topics 判定并降低 confidence。

输入：JSON 数组，每项 { full_name, description, topics }。
只输出一个 JSON 对象，无多余文字、不要 markdown：
{ "results": [ { "full_name": "...", "label": "skill|collection|tool_or_app|unrelated", "confidence": 0.0, "reason": "≤15字" } ] }
results 与输入等长、同序，full_name 原样回填。
"""

DEFAULT_TRANSLATE_PROMPT = """\
把每个 GitHub 仓库描述翻译成简洁的简体中文（保留产品名/专有名词/英文缩写原样）。
若描述本身已是中文，原样返回。不要添加引号或额外说明。

输入：JSON 数组，每项 { full_name, description }。
只输出一个 JSON 对象，无多余文字、不要 markdown：
{ "results": [ { "full_name": "...", "zh": "翻译后的中文" } ] }
results 与输入等长、同序，full_name 原样回填。
"""


def get_classify_prompt(session) -> str:
    return get_plain_setting(session, CLASSIFY_PROMPT_KEY, "") or DEFAULT_CLASSIFY_PROMPT


def get_translate_prompt(session) -> str:
    return get_plain_setting(session, TRANSLATE_PROMPT_KEY, "") or DEFAULT_TRANSLATE_PROMPT


def set_classify_prompt(session, text: str) -> None:
    set_plain_setting(session, CLASSIFY_PROMPT_KEY, text or "")


def set_translate_prompt(session, text: str) -> None:
    set_plain_setting(session, TRANSLATE_PROMPT_KEY, text or "")


def classify_prompt_version(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]
