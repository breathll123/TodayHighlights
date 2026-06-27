import logging
from datetime import datetime, timedelta

from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

_sync_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="aa-sync")
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_session
from app.core.auth import verify_admin, get_current_user
from app.models.entities import AACreatorRegion, AARankingDataset, AARawSnapshot, AASyncRun, User
from app.schemas.artificial_analysis import (
    AACreatorCoverageRead, AACreatorRegionRead, AACreatorRegionUpdate,
    AADatasetStatusRead, AAManualSyncRequest, AASyncRunListRead, AASyncRunRead, AAStatusRead,
)
from app.services.artificial_analysis.repository import (
    get_creator_coverage, get_published_ranking, classify_region, load_manual_overrides,
)
from app.services.artificial_analysis.sync import (ActiveSyncRunError, execute_sync_run,
                                                      request_reparse_run, request_sync_run)
from app.services.audit_logging import log_admin_change

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin/artificial-analysis",
    tags=["artificial-analysis-admin"],
    dependencies=[Depends(verify_admin)],
)


def _serialize_run(run: AASyncRun) -> AASyncRunRead:
    return AASyncRunRead(
        id=run.id,
        trigger_type=run.trigger_type,
        status=run.status,
        requested_datasets=list(run.requested_datasets_json) if run.requested_datasets_json else [],
        completed_datasets=list(run.completed_datasets_json) if run.completed_datasets_json else [],
        failed_datasets=list(run.failed_datasets_json) if run.failed_datasets_json else [],
        request_count=run.request_count,
        quota_tier=run.quota_tier,
        quota_limit=run.quota_limit,
        quota_remaining=run.quota_remaining,
        quota_reset_at=run.quota_reset_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        error_message=run.error_message,
        created_at=run.created_at,
    )


@router.get("/status", response_model=AAStatusRead)
def get_status(session: Session = Depends(get_session)) -> AAStatusRead:
    configured = bool(settings.artificial_analysis_api_key)
    sync_enabled = settings.artificial_analysis_sync_enabled

    # Active run
    active_run = session.scalar(
        select(AASyncRun).where(AASyncRun.status.in_(["pending", "running"])).order_by(AASyncRun.id).limit(1)
    )
    active = _serialize_run(active_run) if active_run else None

    # Quota from latest run
    latest = session.scalar(
        select(AASyncRun).where(AASyncRun.quota_remaining.isnot(None)).order_by(AASyncRun.created_at.desc()).limit(1)
    )
    quota_tier = latest.quota_tier if latest else ""
    quota_limit = latest.quota_limit if latest else None
    quota_remaining = latest.quota_remaining if latest else None
    quota_reset_at = latest.quota_reset_at if latest else None

    # Latest successful
    latest_success = session.scalar(
        select(AASyncRun).where(AASyncRun.status == "succeeded").order_by(AASyncRun.created_at.desc()).limit(1)
    )
    latest_success_run = _serialize_run(latest_success) if latest_success else None

    # Dataset status
    dataset_keys = [
        "language_global", "language_china", "text_to_image", "text_to_video",
        "image_to_video", "text_to_speech", "speech_to_text",
    ]
    datasets: list[AADatasetStatusRead] = []
    for key in dataset_keys:
        ds = session.scalar(
            select(AARankingDataset).where(
                AARankingDataset.dataset_key == key,
                AARankingDataset.status == "published",
            ).order_by(AARankingDataset.published_at.desc()).limit(1)
        )
        is_stale = False
        if ds and ds.captured_at:
            is_stale = ds.captured_at < datetime.utcnow() - timedelta(hours=settings.artificial_analysis_stale_hours)
        datasets.append(AADatasetStatusRead(
            dataset_key=key,
            status=ds.status if ds else "no_data",
            entry_count=ds.entry_count if ds else 0,
            captured_at=ds.captured_at if ds else None,
            published_at=ds.published_at if ds else None,
            is_stale=is_stale,
        ))

    coverage = get_creator_coverage(session)

    return AAStatusRead(
        configured=configured,
        sync_enabled=sync_enabled,
        quota_tier=quota_tier,
        quota_limit=quota_limit,
        quota_remaining=quota_remaining,
        quota_reset_at=quota_reset_at,
        active_run=active,
        latest_successful_run=latest_success_run,
        datasets=datasets,
        creator_coverage=AACreatorCoverageRead(**coverage),
    )


@router.get("/runs", response_model=AASyncRunListRead)
def list_runs(page: int = 1, page_size: int = 20, session: Session = Depends(get_session)) -> AASyncRunListRead:
    total = session.scalar(select(text("COUNT(*) FROM aa_sync_runs")))
    runs = session.scalars(
        select(AASyncRun).order_by(AASyncRun.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return AASyncRunListRead(
        total=total or 0,
        page=page,
        page_size=page_size,
        items=[_serialize_run(r) for r in runs],
    )


@router.get("/runs/{run_id}", response_model=AASyncRunRead)
def get_run(run_id: int, session: Session = Depends(get_session)) -> AASyncRunRead:
    run = session.get(AASyncRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return _serialize_run(run)


@router.get("/creators", response_model=list[AACreatorRegionRead])
def list_creators(session: Session = Depends(get_session)) -> list[AACreatorRegionRead]:
    """
    获取所有创作者的区域划分列表。
    这里会对区域属性进行实时判定（即以数据库中最新的 manual overrides 为最高优先级，否则使用自动判定）。
    这样在后台修改 override 后，查询列表能立刻反应出来，而无需重新运行同步任务。
    """
    overrides = load_manual_overrides(session)
    creators = session.scalars(select(AACreatorRegion).order_by(AACreatorRegion.canonical_name)).all()
    return [AACreatorRegionRead(
        id=c.id,
        creator_external_id=c.creator_external_id,
        canonical_name=c.canonical_name,
        normalized_name=c.normalized_name,
        region_code=classify_region(c.creator_external_id, c.canonical_name, overrides),
        source=c.source,
        notes=c.notes,
    ) for c in creators]


@router.put("/creators/{creator_id}", response_model=AACreatorRegionRead)
def update_creator(
    creator_id: int,
    body: AACreatorRegionUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> AACreatorRegionRead:
    creator = session.get(AACreatorRegion, creator_id)
    if creator is None:
        raise HTTPException(status_code=404, detail="Creator not found")
    creator.region_code = body.region_code
    creator.source = "manual"
    creator.notes = body.notes
    session.commit()
    log_admin_change(
        request=request,
        user=user,
        action="update",
        object_type="aa_creator",
        object_name=creator.canonical_name,
        object_id=creator.id,
        changed_fields=body.model_fields_set,
    )
    return AACreatorRegionRead(
        id=creator.id,
        creator_external_id=creator.creator_external_id,
        canonical_name=creator.canonical_name,
        normalized_name=creator.normalized_name,
        region_code=creator.region_code,
        source=creator.source,
        notes=creator.notes,
    )


@router.post("/sync")
def trigger_sync(
    background_tasks: BackgroundTasks,
    request: Request,
    body: AAManualSyncRequest | None = None,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    try:
        run_id = request_sync_run(
            trigger_type="manual",
            requested_by_user_id=user.id,
            requested_datasets=body.dataset_keys if body else None,
        )
    except ActiveSyncRunError as exc:
        raise HTTPException(
            status_code=409,
            detail={"message": "sync already active", "active_run_id": exc.active_run_id},
        )

    run = session.get(AASyncRun, run_id)
    _sync_executor.submit(execute_sync_run, run_id)
    dataset_names = body.dataset_keys if body and body.dataset_keys else ["全部数据集"]
    log_admin_change(
        request=request,
        user=user,
        action="trigger",
        object_type="aa_sync",
        object_name=",".join(dataset_names),
        object_id=run_id,
        changed_fields=["triggered"],
    )
    return JSONResponse(status_code=202, content={"status": "accepted", "run": _serialize_run(run).model_dump()})
