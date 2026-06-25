"""Skills sync orchestration: upsert generic candidates, snapshot popularity,
classify (cached, re-runs on prompt change), translate kept skills.

Driven two ways:
- `run_provider_sync_inline(session, source_row)` — from `run_crawl_job` (a
  data-source row's 采集), re-fetches candidates then syncs.
- `reparse_existing(session, source)` — the「重新解析」action: re-run AI on the
  rows already in the DB, no provider re-fetch.
"""
from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from sqlalchemy import select

from app.core.config import SH_TZ, settings
from app.core.crypto import CryptoService
from app.core.logging import log_event
# 导入实体模型，新增导入 CrawlJob 任务记录实体模型
from app.models.entities import AIModelConfig, Skill, SkillStat, Source, CrawlJob
from app.services.ai_client import AIClient
from app.services.ai_models import get_default_ai_model
from app.services.skills import classify as _classify
from app.services.skills import prompts as _prompts
from app.services.skills.providers import SITE_TO_SOURCE, fetch_candidates

logger = logging.getLogger("today_highlights.skills")

# Single worker so 采集 + 重新解析 serialize, never overlap or hammer the model.
_job_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="skills-job")


def submit_source_sync(source_id: int) -> None:
    """Background: run the full crawl job (fetch + classify + translate) for a
    skills Source. Used by the admin 采集 button so the request returns fast."""
    def _run() -> None:
        from app.core.database import SessionLocal
        from app.services.jobs import run_crawl_job
        with SessionLocal() as session:
            run_crawl_job(session, source_id, "manual")
    _job_executor.submit(_run)


def submit_reparse(source_id: int) -> None:
    """Background: re-run AI parsing on existing rows (the 重新解析 button).
    接收数据源 ID 并调度后台任务执行，在后台线程中初始化数据库 Session。
    """
    def _run() -> None:
        from app.core.database import SessionLocal
        with SessionLocal() as session:
            reparse_existing(session, source_id)
    _job_executor.submit(_run)


def _now() -> datetime:
    return datetime.now(SH_TZ).replace(tzinfo=None)


def _build_client(session) -> AIClient | None:
    cfg = get_default_ai_model(session) or session.scalar(
        select(AIModelConfig).where(AIModelConfig.enabled.is_(True)).order_by(AIModelConfig.id)
    )
    if cfg is None:
        return None
    api_key = CryptoService(settings.app_secret_key).decrypt(cfg.api_key_encrypted)
    return AIClient(base_url=cfg.base_url, api_key=api_key, model=cfg.model,
                    model_name=cfg.name, task_name="skill 分类/翻译")


def needs_reclassify(skill: Skill, prompt_version: str) -> bool:
    """A skill needs (re)classification if it's never been classified or the
    classify prompt changed since it was classified."""
    return skill.is_skill is None or skill.classify_prompt_version != prompt_version


async def _run_llm(client, skills, classify_prompt, version, translate_prompt, batch, now) -> None:
    await _classify.classify_skills(client, skills, classify_prompt, version, batch, now)
    await _classify.translate_skills(client, skills, translate_prompt, batch, now)


def _upsert(session, source: str, candidates: list[dict], prompt_version: str) -> tuple[list[Skill], list[str]]:
    now = _now()
    ext_ids = [c["external_id"] for c in candidates]
    existing = {
        s.external_id: s
        for s in session.scalars(select(Skill).where(Skill.source == source, Skill.external_id.in_(ext_ids)))
    } if ext_ids else {}

    pending: list[Skill] = []
    for c in candidates:
        skill = existing.get(c["external_id"])
        if skill is None:
            skill = Skill(source=source, external_id=c["external_id"], first_seen_at=now)
            session.add(skill)
            desc_changed = True
        else:
            desc_changed = (skill.description or "") != c["description"]

        skill.name = c["name"]
        skill.author = c["author"]
        skill.url = c["url"]
        skill.language = c["language"]
        skill.description = c["description"]
        skill.popularity = c["popularity"]
        skill.popularity_kind = c["popularity_kind"]
        skill.extra_json = c["extra"]
        skill.last_synced_at = now
        skill.status = "active"

        if desc_changed or needs_reclassify(skill, prompt_version):
            pending.append(skill)

    return pending, ext_ids


def sync_provider(session, source: str, candidates: list[dict]) -> dict:
    """Upsert + snapshot + classify/translate. Returns {candidates, kept, llm}."""
    log_event(logger, channel="application", category="ai", event="skills.sync.started",
              source=source, candidates=len(candidates))
    if not candidates:
        return {"candidates": 0, "kept": 0, "llm": False}

    classify_prompt = _prompts.get_classify_prompt(session)
    translate_prompt = _prompts.get_translate_prompt(session)
    version = _prompts.classify_prompt_version(classify_prompt)

    pending, ext_ids = _upsert(session, source, candidates, version)
    session.flush()  # assign ids for stats + removed query

    now = _now()
    by_ext = {
        s.external_id: s
        for s in session.scalars(select(Skill).where(Skill.source == source, Skill.external_id.in_(ext_ids)))
    }
    for ext in ext_ids:
        skill = by_ext.get(ext)
        if skill is not None:
            session.add(SkillStat(skill_id=skill.id, popularity=skill.popularity, captured_at=now))

    client = _build_client(session)
    if pending and client is None:
        log_event(logger, channel="application", category="ai", level=logging.WARNING,
                  event="skills.classify.skipped_no_model", source=source, pending=len(pending),
                  hint="未配置可用的 AI 模型，候选无法分类，排行将为空")
    elif client is not None and pending:
        batch = settings.github_skills_classify_batch
        asyncio.run(_run_llm(client, pending, classify_prompt, version, translate_prompt, batch, now))

    for skill in session.scalars(
        select(Skill).where(Skill.source == source, Skill.status == "active", Skill.external_id.notin_(ext_ids))
    ):
        skill.status = "removed"

    session.commit()
    kept = sum(1 for s in pending if s.is_skill)
    summary = {"candidates": len(candidates), "kept": kept, "llm": client is not None}
    log_event(logger, channel="application", category="ai", event="skills.sync.completed", source=source, **summary)
    return summary


def run_provider_sync_inline(session, source_row: Source) -> dict:
    """Re-fetch from the provider then sync. Called by run_crawl_job."""
    source = SITE_TO_SOURCE.get(source_row.site)
    if source is None:
        raise ValueError(f"not a skills source: {source_row.site}")
    candidates = fetch_candidates(source)
    return sync_provider(session, source, candidates)


def reparse_existing(session, source_id: int) -> dict:
    """「重新解析」: 针对已有库中的数据，使用当前修改过的 prompt 重新进行 AI 分类和翻译（不重新抓取）。
    通过 CrawlJob 将重新解析的执行过程与状态绑定，并让“任务”页面能够实时跟踪该重新解析进度。
    """
    source_row = session.get(Source, source_id)
    if source_row is None:
        raise ValueError(f"Source not found: {source_id}")
    
    source = SITE_TO_SOURCE.get(source_row.site)
    if source is None:
        raise ValueError(f"Not a skills source: {source_row.site}")

    # 1. 创建 CrawlJob 并立即提交到数据库以供前端在任务列表里查到 running 状态的进程
    job = CrawlJob(
        source_id=source_id,
        trigger_type="reparse",
        status="running",
        started_at=datetime.now(SH_TZ)
    )
    session.add(job)
    session.commit()

    try:
        skills = list(session.scalars(
            select(Skill).where(Skill.source == source, Skill.status == "active")
        ))
        if not skills:
            # 更新状态为成功，并记录未找到任何已入库的待处理技能数据
            job.status = "success"
            job.items_found = 0
            job.items_saved = 0
            job.finished_at = datetime.now(SH_TZ)
            session.commit()
            return {"reparsed": 0, "kept": 0, "llm": False}

        classify_prompt = _prompts.get_classify_prompt(session)
        translate_prompt = _prompts.get_translate_prompt(session)
        version = _prompts.classify_prompt_version(classify_prompt)

        # 强制更新：清空原有缓存的中文描述，使它们进入 LLM 翻译通道
        for skill in skills:
            skill.description_zh = ""

        client = _build_client(session)
        if client is None:
            # 无可用模型时，默认也是一次成功解析但无法使用大模型归档的运行
            job.status = "success"
            job.items_found = len(skills)
            job.items_saved = 0
            job.finished_at = datetime.now(SH_TZ)
            session.commit()
            log_event(logger, channel="application", category="ai", level=logging.WARNING,
                      event="skills.reparse.skipped_no_model", source=source, count=len(skills))
            return {"reparsed": len(skills), "kept": 0, "llm": False}

        batch = settings.github_skills_classify_batch
        asyncio.run(_run_llm(client, skills, classify_prompt, version, translate_prompt, batch, _now()))
        
        # 统计经过大模型过滤后保留的 AI 技能数量
        kept = sum(1 for s in skills if s.is_skill)
        
        # 2. 正常执行完成后更新状态为成功并记录分类结果
        job.status = "success"
        job.items_found = len(skills)
        job.items_saved = kept
        job.finished_at = datetime.now(SH_TZ)
        session.commit()

        log_event(logger, channel="application", category="ai", event="skills.reparse.completed",
                  source=source, reparsed=len(skills), kept=kept)
        return {"reparsed": len(skills), "kept": kept, "llm": True}
        
    except Exception as exc:
        # 3. 发生异常时，记录错误信息并标记任务状态为 failed
        job.status = "failed"
        job.error_message = str(exc)
        job.log_excerpt = str(exc)[:500]
        job.finished_at = datetime.now(SH_TZ)
        session.commit()
        
        log_event(logger, channel="application", category="ai", event="skills.reparse.failed",
                  level=logging.ERROR, source=source, error=str(exc))
        raise
