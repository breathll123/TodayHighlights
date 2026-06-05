import asyncio
import json
from datetime import datetime, timedelta
from hashlib import sha256

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import CryptoService
from app.models.entities import AIGenerationJob, AIBlockAnalysis, AITokenUsage, PageBlock, User
from app.schemas.ai_block_analysis import BlockAnalysisValidated
from app.services.ai_client import AIClient, PostJson
from app.services.ai_models import get_default_ai_model
from app.services.blocks import resolve_block_data

BLOCK_ANALYSIS_TTL_MINUTES = 60
BLOCK_ANALYSIS_SYSTEM_PROMPT = (
    "你是 DataFlow 的区块级信息分析助手。只基于用户提供的方块内容分析，不能补充外部事实。"
    "输出 JSON：summary_points, key_changes, risk_points, related_entities, confidence。"
    "summary_points 根据复杂度输出 1-4 条。股票类不得给买入、卖出、持有建议。"
)


def _trim_list(values: object, max_items: int, max_chars: int) -> list[str]:
    if not isinstance(values, list):
        return []
    result: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        text = value.strip()
        if text:
            result.append(text[:max_chars])
        if len(result) >= max_items:
            break
    return result


def validate_block_analysis_payload(payload: dict) -> BlockAnalysisValidated:
    summary_points = _trim_list(payload.get("summary_points"), 4, 160)
    if not summary_points:
        raise ValueError("summary_points is required")
    confidence = payload.get("confidence", 0)
    if not isinstance(confidence, int | float):
        raise ValueError("confidence must be a number")
    confidence = max(0.0, min(1.0, float(confidence)))
    return BlockAnalysisValidated(
        summary_points=summary_points,
        key_changes=_trim_list(payload.get("key_changes"), 3, 140),
        risk_points=_trim_list(payload.get("risk_points"), 2, 140),
        related_entities=_trim_list(payload.get("related_entities"), 8, 40),
        confidence=confidence,
    )


def build_block_data_hash(data: list[dict]) -> str:
    normalized = json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)
    return sha256(normalized.encode()).hexdigest()


def build_evidence_refs(data: list[dict]) -> list[dict]:
    refs: list[dict] = []
    for item in data[:12]:
        refs.append(
            {
                "title": str(item.get("title") or item.get("name") or "")[:160],
                "source": str(item.get("source") or item.get("source_type") or "")[:80],
                "published_at": item.get("published_at") or item.get("created_at") or item.get("time"),
                "url": item.get("url"),
            }
        )
    return refs


def block_user_prompt(block: PageBlock, data: list[dict]) -> str:
    compact = [
        {
            "title": item.get("title") or item.get("name"),
            "summary": item.get("summary") or item.get("content"),
            "tags": item.get("tags") or item.get("tags_json"),
            "metrics": item.get("metrics") or {k: item.get(k) for k in ("score", "percent", "rank", "status")},
        }
        for item in data[:20]
    ]
    return json.dumps(
        {"block_title": block.title, "source_type": block.source_type, "items": compact},
        ensure_ascii=False,
    )


def find_cached_analysis(session: Session, page_route: str, block_id: int, data_hash: str) -> AIBlockAnalysis | None:
    now = datetime.utcnow()
    return session.scalar(
        select(AIBlockAnalysis)
        .where(
            AIBlockAnalysis.page_route == page_route,
            AIBlockAnalysis.block_id == block_id,
            AIBlockAnalysis.data_hash == data_hash,
            AIBlockAnalysis.status == "generated",
            AIBlockAnalysis.expires_at > now,
        )
        .order_by(AIBlockAnalysis.generated_at.desc())
        .limit(1)
    )


def analyze_block(
    session: Session,
    *,
    user: User,
    page_route: str,
    block_id: int,
    post_json: PostJson | None = None,
    force: bool = False,
    resolved_data: list[dict] | None = None,
) -> AIBlockAnalysis:
    block = session.get(PageBlock, block_id)
    if block is None or block.page_route != page_route or not block.enabled or block.status != "published":
        raise HTTPException(status_code=404, detail="Block not found")
    data = resolved_data if resolved_data is not None else resolve_block_data(session, block)
    data_hash = build_block_data_hash(data)
    if not force:
        cached = find_cached_analysis(session, page_route, block_id, data_hash)
        if cached is not None:
            return cached

    model_cfg = get_default_ai_model(session)
    if model_cfg is None:
        raise HTTPException(status_code=400, detail="No default AI model configured")

    analysis = AIBlockAnalysis(
        page_route=page_route,
        block_id=block.id,
        block_title=block.title,
        source_type=block.source_type,
        data_hash=data_hash,
        status="processing",
        generated_by_user_id=user.id,
        model_config_id=model_cfg.id,
        expires_at=datetime.utcnow() + timedelta(minutes=BLOCK_ANALYSIS_TTL_MINUTES),
    )
    session.add(analysis)
    session.flush()

    job = AIGenerationJob(
        job_type="block_analysis",
        trigger_type="manual" if not force else "regenerate",
        status="processing",
        user_id=user.id,
        block_analysis_id=analysis.id,
        model_config_id=model_cfg.id,
        input_count=len(data),
        started_at=datetime.utcnow(),
    )
    session.add(job)
    session.flush()

    try:
        crypto = CryptoService(settings.app_secret_key)
        client = AIClient(model_cfg.base_url, crypto.decrypt(model_cfg.api_key_encrypted), model_cfg.model, post_json=post_json)
        prompt = block_user_prompt(block, data)
        result = asyncio.run(client.complete_json_with_usage(BLOCK_ANALYSIS_SYSTEM_PROMPT, prompt))
        validated = validate_block_analysis_payload(result.content)

        analysis.summary_points_json = validated.summary_points
        analysis.key_changes_json = validated.key_changes
        analysis.risk_points_json = validated.risk_points
        analysis.related_entities_json = validated.related_entities
        analysis.evidence_refs_json = build_evidence_refs(data)
        analysis.generated_by_model = model_cfg.model
        analysis.generated_at = datetime.utcnow()
        analysis.status = "generated"
        job.status = "succeeded"
        job.success_count = 1
        job.finished_at = datetime.utcnow()

        usage = AITokenUsage(
            user_id=user.id,
            model_config_id=model_cfg.id,
            model_name=model_cfg.model,
            usage_type="block_analysis",
            prompt_tokens=result.usage["prompt_tokens"],
            completion_tokens=result.usage["completion_tokens"],
            total_tokens=result.usage["total_tokens"],
            estimated=result.usage_estimated,
            request_status="success",
            related_job_id=job.id,
            related_block_analysis_id=analysis.id,
        )
        session.add(usage)
        session.flush()
        analysis.token_usage_id = usage.id
    except Exception as exc:
        analysis.status = "failed"
        analysis.error_message = str(exc)[:500]
        job.status = "failed"
        job.failed_count = 1
        job.error_message = str(exc)[:500]
        job.finished_at = datetime.utcnow()
    session.flush()
    return analysis
