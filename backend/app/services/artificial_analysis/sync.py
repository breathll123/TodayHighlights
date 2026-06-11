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
from app.models.entities import AASyncRun
from app.services.artificial_analysis.collector import (ArtificialAnalysisCollector, QuotaReserveReached,
                                                           UpstreamRateLimited, create_default_client)
from app.services.artificial_analysis.constants import DATASETS, SYNC_DATASET_ORDER
from app.services.artificial_analysis.parser import DatasetParseError, derive_china_dataset, parse_dataset
from app.services.artificial_analysis.repository import (get_published_ranking, load_creator_regions,
                                                            mark_abandoned_runs, observe_unknown_creators,
                                                            publish_dataset, store_parsed_dataset)

logger = logging.getLogger(__name__)

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
            logger.warning("sync run %d could not acquire lock", run_id)
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

            collector = ArtificialAnalysisCollector(session, client_factory=client_factory)
            requested = list(run.requested_datasets_json) if run.requested_datasets_json else list(SYNC_DATASET_ORDER)
            completed: list[str] = []
            failed: list[dict] = []

            for dataset_key in requested:
                definition = DATASETS.get(dataset_key)
                if definition is None:
                    continue

                try:
                    collected = collector.collect(run, definition)
                    if not collected.payloads:
                        failed.append({"key": dataset_key, "error": "no payloads collected"})
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

                    # Derive China dataset for language_global
                    if dataset_key == "language_global":
                        try:
                            china = derive_china_dataset(parsed)
                            observe_unknown_creators(session, china.entries)
                            china_ds = store_parsed_dataset(
                                session,
                                run_id=run_id,
                                parsed=china,
                                snapshot_ids=collected.snapshot_ids,
                                captured_at=datetime.utcnow(),
                            )
                            session.commit()
                            publish_dataset(session, china_ds.id)
                            completed.append("language_china")
                        except DatasetParseError as exc:
                            logger.warning("China derivation failed: %s", exc)

                    completed.append(dataset_key)
                    session.commit()
                    run.heartbeat_at = datetime.utcnow()
                    session.commit()

                except (QuotaReserveReached, UpstreamRateLimited) as exc:
                    failed.append({"key": dataset_key, "error": str(exc)})
                    run.quota_remaining = 0
                    break
                except Exception as exc:
                    logger.exception("dataset %s failed", dataset_key)
                    failed.append({"key": dataset_key, "error": str(exc)})

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

        except Exception as exc:
            logger.exception("sync run %d fatal error", run_id)
            try:
                run = session.get(AASyncRun, run_id)
                if run:
                    run.status = "failed"
                    run.error_message = str(exc)
                    run.finished_at = datetime.utcnow()
                    session.commit()
            except Exception:
                pass
        finally:
            session.close()


def scheduled_sync() -> None:
    """Entry point for APScheduler."""
    if not settings.artificial_analysis_sync_enabled:
        return
    if not settings.artificial_analysis_api_key:
        logger.warning("Artificial Analysis API key not configured")
        return

    try:
        run_id = request_sync_run(trigger_type="scheduled")
    except ActiveSyncRunError:
        logger.info("Scheduled sync skipped — another run is active")
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
