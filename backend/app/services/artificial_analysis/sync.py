import logging
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Callable

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.core.logging import bind_log_context, log_event
from app.models.entities import AASyncRun
from app.services.artificial_analysis.collector import (ArtificialAnalysisCollector, QuotaReserveReached,
                                                           UpstreamRateLimited, create_default_client)
from app.services.artificial_analysis.constants import DATASETS, SYNC_DATASET_ORDER
from app.services.artificial_analysis.parser import parse_dataset
from app.services.artificial_analysis.repository import (get_published_ranking, load_creator_regions,
                                                            mark_abandoned_runs, observe_unknown_creators,
                                                            publish_dataset, store_parsed_dataset)

logger = logging.getLogger("today_highlights.artificial_analysis")

LOCK_NAME = "today-highlights:artificial-analysis-sync"
_TEST_PROCESS_LOCK = threading.Lock()


class ActiveSyncRunError(RuntimeError):
    def __init__(self, active_run_id: int):
        super().__init__("Artificial Analysis sync already active")
        self.active_run_id = active_run_id


@contextmanager
def artificial_analysis_lock(*, timeout_seconds: int = 0):
    """Acquire a MySQL advisory lock or process-local lock for SQLite."""
    connection = engine.connect()
    try:
        if connection.dialect.name == "mysql":
            acquired = connection.scalar(
                text("SELECT GET_LOCK(:name, :timeout)"),
                {"name": LOCK_NAME, "timeout": timeout_seconds},
            )
            if acquired != 1:
                yield False
                return
            try:
                yield True
            finally:
                connection.execute(
                    text("SELECT RELEASE_LOCK(:name)"),
                    {"name": LOCK_NAME},
                )
        else:
            with _TEST_PROCESS_LOCK:
                yield True
    finally:
        connection.close()


def create_sync_run(
    session: Session,
    *,
    trigger_type: str,
    requested_by_user_id: int | None = None,
    requested_datasets: list[str] | None = None,
) -> AASyncRun:
    """Insert a new pending sync run."""
    if requested_datasets is None:
        requested_datasets = list(SYNC_DATASET_ORDER)

    run = AASyncRun(
        trigger_type=trigger_type,
        status="pending",
        requested_by_user_id=requested_by_user_id,
        requested_datasets_json=requested_datasets,
    )
    session.add(run)
    session.flush()
    return run


def request_sync_run(
    *,
    trigger_type: str,
    requested_by_user_id: int | None = None,
    requested_datasets: list[str] | None = None,
) -> int:
    """Create a pending run under advisory lock. Returns run ID."""
    with artificial_analysis_lock(timeout_seconds=0) as acquired:
        if not acquired:
            raise ActiveSyncRunError(0)

        session = SessionLocal()
        try:
            mark_abandoned_runs(session)

            active = session.scalars(
                text("SELECT id FROM aa_sync_runs WHERE status IN ('pending', 'running') ORDER BY id LIMIT 1")
            ).first()
            if active is not None:
                raise ActiveSyncRunError(active[0] if isinstance(active, tuple) else active)

            run = create_sync_run(
                session,
                trigger_type=trigger_type,
                requested_by_user_id=requested_by_user_id,
                requested_datasets=requested_datasets,
            )
            session.commit()
            log_event(
                logger,
                channel="application",
                category="ai",
                event="aa.sync.requested",
                ai_job_id=run.id,
                user_id=requested_by_user_id,
                trigger_type=trigger_type,
                dataset_count=len(run.requested_datasets_json),
            )
            return run.id
        finally:
            session.close()


def execute_sync_run(
    run_id: int,
    *,
    client_factory: Callable[[], httpx.Client] = create_default_client,
) -> None:
    """Execute a previously created sync run to completion."""
    with artificial_analysis_lock(timeout_seconds=0) as acquired:
        if not acquired:
            log_event(
                logger,
                channel="application",
                category="ai",
                event="aa.sync.skipped",
                level=logging.WARNING,
                ai_job_id=run_id,
                reason="lock",
            )
            return

        session = SessionLocal()
        try:
            mark_abandoned_runs(session)

            run = session.get(AASyncRun, run_id)
            if run is None:
                return
            if run.status == "abandoned":
                return

            run.status = "running"
            run.started_at = datetime.utcnow()
            run.heartbeat_at = datetime.utcnow()
            session.commit()

            with bind_log_context(ai_job_id=run.id, user_id=run.requested_by_user_id):
                log_event(
                    logger,
                    channel="application",
                    category="ai",
                    event="aa.sync.started",
                    trigger_type=run.trigger_type,
                )

                collector = ArtificialAnalysisCollector(session, client_factory=client_factory)
                requested = list(run.requested_datasets_json) if run.requested_datasets_json else list(SYNC_DATASET_ORDER)
                completed: list[str] = []
                failed: list[dict] = []

                for dataset_key in requested:
                    definition = DATASETS.get(dataset_key)
                    if definition is None:
                        continue

                    log_event(
                        logger,
                        channel="application",
                        category="ai",
                        event="aa.dataset.started",
                        dataset_key=dataset_key,
                    )
                    try:
                        collected = collector.collect(run, definition)
                        if not collected.payloads:
                            failed.append({"key": dataset_key, "error": "no payloads collected"})
                            log_event(
                                logger,
                                channel="application",
                                category="ai",
                                event="aa.dataset.failed",
                                level=logging.WARNING,
                                dataset_key=dataset_key,
                                reason="no_payloads",
                            )
                            continue

                        regions = load_creator_regions(session)
                        parsed = parse_dataset(dataset_key, collected.payloads, regions)

                        observe_unknown_creators(session, parsed.entries)

                        dataset = store_parsed_dataset(
                            session,
                            run_id=run_id,
                            parsed=parsed,
                            snapshot_ids=collected.snapshot_ids,
                            captured_at=datetime.utcnow(),
                        )
                        session.commit()
                        publish_dataset(session, dataset.id)



                        completed.append(dataset_key)
                        run.heartbeat_at = datetime.utcnow()
                        session.commit()
                        log_event(
                            logger,
                            channel="application",
                            category="ai",
                            event="aa.dataset.completed",
                            dataset_key=dataset_key,
                            dataset_id=dataset.id,
                            entry_count=len(parsed.entries),
                            snapshot_count=len(collected.snapshot_ids),
                        )

                    except (QuotaReserveReached, UpstreamRateLimited) as exc:
                        failed.append({"key": dataset_key, "error": str(exc)})
                        run.quota_remaining = 0
                        log_event(
                            logger,
                            channel="application",
                            category="ai",
                            event="aa.dataset.failed",
                            level=logging.WARNING,
                            dataset_key=dataset_key,
                            error_type=type(exc).__name__,
                            error=str(exc),
                        )
                        break
                    except Exception as exc:
                        failed.append({"key": dataset_key, "error": str(exc)})
                        log_event(
                            logger,
                            channel="application",
                            category="ai",
                            event="aa.dataset.failed",
                            level=logging.ERROR,
                            dataset_key=dataset_key,
                            error_type=type(exc).__name__,
                            error=str(exc),
                            exc_info=True,
                        )

            run.completed_datasets_json = completed
            run.failed_datasets_json = failed

            if not completed:
                run.status = "failed" if failed else "quota_exhausted"
            elif failed:
                run.status = "partial"
            else:
                run.status = "succeeded"

            run.finished_at = datetime.utcnow()
            session.commit()
            log_event(
                logger,
                channel="application",
                category="ai",
                event="aa.sync.completed",
                ai_job_id=run.id,
                user_id=run.requested_by_user_id,
                status=run.status,
                completed_count=len(completed),
                failed_count=len(failed),
                request_count=run.request_count,
            )

        except Exception as exc:
            log_event(
                logger,
                channel="error",
                category="ai",
                event="aa.sync.failed",
                level=logging.ERROR,
                ai_job_id=run_id,
                error_type=type(exc).__name__,
                error=str(exc),
                exc_info=True,
            )
            try:
                run = session.get(AASyncRun, run_id)
                if run:
                    run.status = "failed"
                    run.error_message = str(exc)
                    run.finished_at = datetime.utcnow()
                    session.commit()
            except Exception as persist_exc:
                log_event(
                    logger,
                    channel="error",
                    category="ai",
                    event="aa.sync.status-persist.failed",
                    level=logging.ERROR,
                    ai_job_id=run_id,
                    error_type=type(persist_exc).__name__,
                )
        finally:
            session.close()


def scheduled_sync() -> None:
    """Entry point for APScheduler."""
    if not settings.artificial_analysis_sync_enabled:
        log_event(
            logger,
            channel="application",
            category="ai",
            event="aa.sync.skipped",
            reason="disabled",
            trigger_type="scheduled",
        )
        return
    if not settings.artificial_analysis_api_key:
        log_event(
            logger,
            channel="application",
            category="ai",
            event="aa.sync.skipped",
            level=logging.WARNING,
            reason="missing_api_key",
            trigger_type="scheduled",
        )
        return

    try:
        run_id = request_sync_run(trigger_type="scheduled")
    except ActiveSyncRunError as exc:
        log_event(
            logger,
            channel="application",
            category="ai",
            event="aa.sync.skipped",
            reason="active_run",
            trigger_type="scheduled",
            active_run_id=exc.active_run_id,
        )
        return

    execute_sync_run(run_id)


def request_reparse_run(*, snapshot_id: int, requested_by_user_id: int) -> int:
    """Create a reparse run for an existing snapshot. Returns run ID."""
    with artificial_analysis_lock(timeout_seconds=0) as acquired:
        if not acquired:
            raise ActiveSyncRunError(0)

        session = SessionLocal()
        try:
            mark_abandoned_runs(session)

            active = session.execute(
                text("SELECT id FROM aa_sync_runs WHERE status IN ('pending', 'running') ORDER BY id LIMIT 1")
            ).first()
            if active is not None:
                rid = active[0] if isinstance(active, tuple) else active
                raise ActiveSyncRunError(rid)

            run = AASyncRun(
                trigger_type="reparse",
                status="pending",
                requested_by_user_id=requested_by_user_id,
                requested_datasets_json=[],
            )
            session.add(run)
            session.commit()
            return run.id
        finally:
            session.close()
