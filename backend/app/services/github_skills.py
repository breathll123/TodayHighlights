"""Daily sync for the GitHub skills ranking.

Pipeline: fetch top-K candidates by stars → upsert + daily stats snapshot →
LLM-classify the new/changed ones (cached) → LLM-translate kept skills'
descriptions to Chinese (cached, skips already-Chinese). The request-time
block reads the resulting `github_skill_repos` rows directly.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from sqlalchemy import select

from app.core.config import SH_TZ, settings
from app.core.crypto import CryptoService
from app.core.database import SessionLocal
from app.core.logging import log_event
from app.models.entities import AIModelConfig, GithubSkillRepo, GithubSkillStat
from app.services.adapters.github import fetch_skill_candidates
from app.services.ai_client import AIClient
from app.services.ai_models import get_default_ai_model
from app.services.settings import get_plain_setting, set_plain_setting

logger = logging.getLogger("today_highlights.github_skills")

SYNC_ENABLED_KEY = "github_skills.sync_enabled"

# Single-worker executor so manual + scheduled syncs serialize, never overlap.
_sync_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gh-skills-sync")
_sync_lock = threading.Lock()
_sync_running = False

# 核心仓库分类提示词：用于指示大模型对获取到的 GitHub 仓库进行二次筛选分类。
# 现已支持将“用于开发、运行、管理 AI agent skills 的专属框架/SDK”一并划分到 skill 标签进行保留。
CLASSIFY_SYSTEM_PROMPT = """\
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

TRANSLATE_SYSTEM_PROMPT = """\
把每个 GitHub 仓库描述翻译成简洁的简体中文（保留产品名/专有名词/英文缩写原样）。
若描述本身已是中文，原样返回。不要添加引号或额外说明。

输入：JSON 数组，每项 { full_name, description }。
只输出一个 JSON 对象，无多余文字、不要 markdown：
{ "results": [ { "full_name": "...", "zh": "翻译后的中文" } ] }
results 与输入等长、同序，full_name 原样回填。
"""

_VALID_LABELS = {"skill", "collection", "tool_or_app", "unrelated"}


def _now() -> datetime:
    return datetime.now(SH_TZ).replace(tzinfo=None)


def _has_chinese(text: str) -> bool:
    return any("一" <= ch <= "鿿" for ch in text)


def _chunked(items: list, size: int) -> list[list]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def _upsert_candidates(session, candidates: list[dict]) -> tuple[list[GithubSkillRepo], set[int]]:
    """Insert/update repos. Returns (repos_needing_classification, candidate_ids).
    A repo needs (re)classification if it's new or its description changed."""
    now = _now()
    ids = [c["id"] for c in candidates]
    existing = {
        r.id: r for r in session.scalars(select(GithubSkillRepo).where(GithubSkillRepo.id.in_(ids)))
    } if ids else {}

    pending: list[GithubSkillRepo] = []
    for c in candidates:
        repo = existing.get(c["id"])
        desc_changed = False
        if repo is None:
            repo = GithubSkillRepo(id=c["id"], first_seen_at=now)
            session.add(repo)
            desc_changed = True
        else:
            desc_changed = (repo.description or "") != c["description"]
            repo.topics_matched_json = sorted(set(repo.topics_matched_json or []) | set(c["topics_matched"]))

        repo.full_name = c["full_name"]
        repo.owner = c["owner"]
        repo.name = c["name"]
        repo.url = c["url"]
        repo.language = c["language"]
        repo.topics_json = c["topics"]
        if repo.id not in existing:
            repo.topics_matched_json = c["topics_matched"]
        repo.stars = c["stars"]
        repo.forks = c["forks"]
        repo.pushed_at = c["pushed_at"]
        repo.description = c["description"]
        repo.last_synced_at = now
        repo.status = "active"

        if desc_changed or repo.is_skill is None:
            pending.append(repo)

        session.add(GithubSkillStat(repo_id=repo.id, stars=c["stars"], forks=c["forks"], captured_at=now))

    return pending, set(ids)


async def _classify(client: AIClient, repos: list[GithubSkillRepo], batch_size: int) -> None:
    model = client.model_name
    now = _now()
    for batch in _chunked(repos, batch_size):
        payload = [{"full_name": r.full_name, "description": r.description, "topics": r.topics_json} for r in batch]
        try:
            result = await client.complete_json(CLASSIFY_SYSTEM_PROMPT, json.dumps(payload, ensure_ascii=False))
        except Exception as exc:  # noqa: BLE001 — log + skip batch, keep syncing
            log_event(logger, channel="application", category="ai", event="github_skills.classify.failed",
                      level=logging.ERROR, error_type=type(exc).__name__, error=str(exc), batch_size=len(batch))
            continue
        verdicts = {v.get("full_name"): v for v in result.get("results", [])}
        for repo in batch:
            v = verdicts.get(repo.full_name)
            if not v:
                continue
            label = v.get("label") if v.get("label") in _VALID_LABELS else "unrelated"
            repo.skill_kind = label
            repo.is_skill = label == "skill"
            repo.classify_reason = (v.get("reason") or "")[:120]
            repo.classified_by_model = model
            repo.classified_at = now


async def _translate(client: AIClient, repos: list[GithubSkillRepo], batch_size: int) -> None:
    model = client.model_name
    now = _now()
    # Repos that are kept skills and still need a Chinese description.
    todo = [r for r in repos if r.is_skill and (not r.description_zh or r.description_zh.strip() == "")]
    pending_llm: list[GithubSkillRepo] = []
    for repo in todo:
        if not repo.description:
            repo.description_zh = ""
        elif _has_chinese(repo.description):
            repo.description_zh = repo.description
            repo.translated_by_model = "zh-native"
            repo.translated_at = now
        else:
            pending_llm.append(repo)

    for batch in _chunked(pending_llm, batch_size):
        payload = [{"full_name": r.full_name, "description": r.description} for r in batch]
        try:
            result = await client.complete_json(TRANSLATE_SYSTEM_PROMPT, json.dumps(payload, ensure_ascii=False))
        except Exception as exc:  # noqa: BLE001
            log_event(logger, channel="application", category="ai", event="github_skills.translate.failed",
                      level=logging.ERROR, error_type=type(exc).__name__, error=str(exc), batch_size=len(batch))
            continue
        zh_by_name = {v.get("full_name"): (v.get("zh") or "").strip() for v in result.get("results", [])}
        for repo in batch:
            zh = zh_by_name.get(repo.full_name)
            if zh:
                repo.description_zh = zh
                repo.translated_by_model = model
                repo.translated_at = now


def _build_client(session) -> AIClient | None:
    cfg = get_default_ai_model(session) or session.scalar(
        select(AIModelConfig).where(AIModelConfig.enabled.is_(True)).order_by(AIModelConfig.id)
    )
    if cfg is None:
        return None
    api_key = CryptoService(settings.app_secret_key).decrypt(cfg.api_key_encrypted)
    return AIClient(base_url=cfg.base_url, api_key=api_key, model=cfg.model,
                    model_name=cfg.name, task_name="skill 分类/翻译")


def sync_github_skills(session) -> dict:
    """Run one full sync. Returns a small summary dict."""
    log_event(logger, channel="application", category="ai", event="github_skills.sync.started")
    candidates = fetch_skill_candidates()
    if not candidates:
        log_event(logger, channel="application", category="ai", event="github_skills.sync.empty",
                  level=logging.WARNING)
        return {"candidates": 0, "classified": 0, "kept": 0}

    pending, candidate_ids = _upsert_candidates(session, candidates)
    session.flush()

    client = _build_client(session)
    if pending and client is None:
        log_event(logger, channel="application", category="ai", level=logging.WARNING,
                  event="github_skills.classify.skipped_no_model", pending=len(pending),
                  hint="未配置可用的 AI 模型，候选无法分类，排行将为空")
    elif client is not None and pending:
        batch = settings.github_skills_classify_batch
        asyncio.run(_run_llm(client, pending, batch))

    # Repos that dropped out of the top-K candidate set go dormant (kept for history).
    if candidate_ids:
        for repo in session.scalars(
            select(GithubSkillRepo).where(GithubSkillRepo.status == "active", GithubSkillRepo.id.notin_(candidate_ids))
        ):
            repo.status = "removed"

    session.commit()

    kept = sum(1 for r in pending if r.is_skill)
    summary = {"candidates": len(candidates), "classified": len(pending), "kept": kept,
               "llm": client is not None}
    log_event(logger, channel="application", category="ai", event="github_skills.sync.completed", **summary)
    return summary


async def _run_llm(client: AIClient, repos: list[GithubSkillRepo], batch_size: int) -> None:
    await _classify(client, repos, batch_size)
    await _translate(client, repos, batch_size)


# ── Enable flag (stored in app_settings, toggled from the admin UI) ──

def is_sync_enabled(session) -> bool:
    return get_plain_setting(session, SYNC_ENABLED_KEY, "false") == "true"


def set_sync_enabled(session, enabled: bool) -> None:
    set_plain_setting(session, SYNC_ENABLED_KEY, "true" if enabled else "false")
    session.commit()


# ── Background runner (manual button + daily cron both go through here) ──

def is_sync_running() -> bool:
    with _sync_lock:
        return _sync_running


def run_sync_now() -> None:
    """Run one sync with its own session, guarded so two can't overlap."""
    global _sync_running
    with _sync_lock:
        if _sync_running:
            return
        _sync_running = True
    try:
        with SessionLocal() as session:
            sync_github_skills(session)
    finally:
        with _sync_lock:
            _sync_running = False


def trigger_sync_async() -> bool:
    """Submit a background sync. Returns False if one is already running."""
    if is_sync_running():
        return False
    _sync_executor.submit(run_sync_now)
    return True


def scheduled_sync() -> None:
    """Daily cron entry: only runs when the admin toggle is on."""
    with SessionLocal() as session:
        enabled = is_sync_enabled(session)
    if not enabled:
        log_event(logger, channel="application", category="scheduler",
                  event="github_skills.sync.skipped_disabled")
        return
    run_sync_now()
