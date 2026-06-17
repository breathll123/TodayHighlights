from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_session
from app.models.entities import AIBlockAnalysis, AITokenUsage, User
from app.schemas.ai_block_analysis import BlockAnalysisRead
from app.services.ai_block_analysis import analyze_block

router = APIRouter(prefix="/api/ai", tags=["ai"])

MAX_VISIBLE_DATA_ITEMS = 200
ALLOWED_VISIBLE_DATA_FIELDS = {
    "id",
    "title",
    "name",
    "summary",
    "content",
    "source",
    "source_type",
    "published_at",
    "created_at",
    "url",
    "rank",
    "score",
    "percent",
    "value",
    "tags",
    "tags_json",
    "related_symbols_json",
    "symbols",
    "team",
    "league",
    "group",
    "season",
    "updated",
    "gp",
    "pts",
    "wdl",
    "gf",
    "ga",
    "gd",
    "status",
    "minute",
    "start_time",
    "team_a",
    "team_b",
    "score_a",
    "score_b",
    "model",
    "creator",
    "subtitle",
    "region",
    "net_amount",
    "reason",
}


def _safe_visible_value(value: object) -> object:
    if isinstance(value, str):
        return value[:500]
    if isinstance(value, int | float | bool) or value is None:
        return value
    if isinstance(value, list):
        safe_list = []
        for item in value[:12]:
            if isinstance(item, str):
                safe_list.append(item[:120])
            elif isinstance(item, int | float | bool) or item is None:
                safe_list.append(item)
        return safe_list
    return None


def _visible_data_from_payload(value: object) -> list[dict] | None:
    if not isinstance(value, list):
        return None
    result: list[dict] = []
    for raw_item in value[:MAX_VISIBLE_DATA_ITEMS]:
        if not isinstance(raw_item, dict):
            continue
        item: dict = {}
        for key in ALLOWED_VISIBLE_DATA_FIELDS:
            if key not in raw_item:
                continue
            safe_value = _safe_visible_value(raw_item.get(key))
            if safe_value is not None:
                item[key] = safe_value
        if item:
            result.append(item)
    return result


def _read_analysis(session: Session, analysis: AIBlockAnalysis) -> BlockAnalysisRead:
    usage = session.get(AITokenUsage, analysis.token_usage_id) if analysis.token_usage_id else None
    return BlockAnalysisRead(
        id=analysis.id,
        page_route=analysis.page_route,
        block_id=analysis.block_id,
        block_title=analysis.block_title,
        status=analysis.status,
        summary_points=analysis.summary_points_json,
        key_changes=analysis.key_changes_json,
        risk_points=analysis.risk_points_json,
        related_entities=analysis.related_entities_json,
        evidence_refs=analysis.evidence_refs_json,
        generated_by_model=analysis.generated_by_model,
        prompt_tokens=usage.prompt_tokens if usage else 0,
        completion_tokens=usage.completion_tokens if usage else 0,
        total_tokens=usage.total_tokens if usage else 0,
        token_estimated=usage.estimated if usage else False,
        generated_at=analysis.generated_at,
        expires_at=analysis.expires_at,
    )


@router.get("/block-analyses", response_model=BlockAnalysisRead)
def get_block_analysis(
    page_route: str = Query(...),
    block_id: int = Query(...),
    data_hash: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> BlockAnalysisRead:
    query = select(AIBlockAnalysis).where(
        AIBlockAnalysis.page_route == page_route,
        AIBlockAnalysis.block_id == block_id,
        AIBlockAnalysis.status == "generated",
    )
    if data_hash:
        query = query.where(AIBlockAnalysis.data_hash == data_hash)
    analysis = session.scalar(query.order_by(AIBlockAnalysis.generated_at.desc()).limit(1))
    if analysis is None:
        raise HTTPException(status_code=404, detail="No cached analysis")
    return _read_analysis(session, analysis)


@router.post("/block-analyses", response_model=BlockAnalysisRead)
def create_block_analysis(
    payload: dict,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> BlockAnalysisRead:
    visible_data = _visible_data_from_payload(payload.get("visible_data"))
    analysis = analyze_block(
        session,
        user=user,
        page_route=str(payload.get("page_route", "")),
        block_id=int(payload.get("block_id", 0)),
        resolved_data=visible_data,
        data_scope_label=str(payload.get("scope_label", ""))[:80] or None,
    )
    session.commit()
    return _read_analysis(session, analysis)
