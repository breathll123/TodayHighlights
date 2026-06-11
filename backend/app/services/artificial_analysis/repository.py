import logging
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import AACreatorRegion, AARankingDataset, AARankingEntry, AARawSnapshot, AASyncRun
from app.services.artificial_analysis.parser import ParsedDataset, ParsedRankingEntry

logger = logging.getLogger(__name__)


def load_creator_regions(session: Session) -> list[AACreatorRegion]:
    return list(session.scalars(select(AACreatorRegion)))


def observe_unknown_creators(
    session: Session,
    entries: list[ParsedRankingEntry],
) -> None:
    """Insert observed creator rows for creators not yet in the database."""
    known_ids: set[str] = set()
    known_names: set[str] = set()
    existing = session.scalars(select(AACreatorRegion)).all()
    for cr in existing:
        if cr.creator_external_id:
            known_ids.add(cr.creator_external_id)
        if cr.normalized_name:
            known_names.add(cr.normalized_name)

    for entry in entries:
        if entry.creator_external_id and entry.creator_external_id not in known_ids:
            cr = AACreatorRegion(
                creator_external_id=entry.creator_external_id,
                canonical_name=entry.creator_name,
                normalized_name=entry.creator_name.lower().strip(),
                region_code="unknown",
                source="observed",
            )
            session.add(cr)
            known_ids.add(entry.creator_external_id)
        elif not entry.creator_external_id and entry.creator_name:
            norm = entry.creator_name.lower().strip()
            if norm and norm not in known_names:
                cr = AACreatorRegion(
                    creator_external_id=None,
                    canonical_name=entry.creator_name,
                    normalized_name=norm,
                    region_code="unknown",
                    source="observed",
                )
                session.add(cr)
                known_names.add(norm)


def store_parsed_dataset(
    session: Session,
    *,
    run_id: int,
    parsed: ParsedDataset,
    snapshot_ids: list[int],
    captured_at: datetime,
) -> AARankingDataset:
    """Persist a parsed dataset and its entries as a new immutable version."""
    dataset = AARankingDataset(
        sync_run_id=run_id,
        dataset_key=parsed.dataset_key,
        scope=parsed.scope,
        score_type=parsed.score_type,
        status="ready",
        source_tier=parsed.source_tier,
        source_version=parsed.source_version,
        entry_count=len(parsed.entries),
        source_snapshot_ids_json=snapshot_ids,
        parser_warnings_json=parsed.warnings,
        data_sha256=parsed.data_sha256,
        captured_at=captured_at,
    )
    session.add(dataset)
    session.flush()

    for entry in parsed.entries:
        row = AARankingEntry(
            dataset_id=dataset.id,
            model_external_id=entry.model_external_id,
            model_slug=entry.model_slug,
            model_name=entry.model_name,
            creator_external_id=entry.creator_external_id,
            creator_name=entry.creator_name,
            creator_region=entry.creator_region,
            rank=entry.rank,
            score=entry.score,
            score_type=entry.score_type,
            ci_95=entry.ci_95,
            release_date=entry.release_date,
            metrics_json=entry.metrics,
            pricing_json=entry.pricing,
            performance_json=entry.performance,
            source_url=entry.source_url or f"https://artificialanalysis.ai/",
        )
        session.add(row)

    session.flush()
    return dataset


def publish_dataset(session: Session, dataset_id: int) -> AARankingDataset:
    """Atomically publish one dataset, superseding the previous version."""
    dataset = session.get(AARankingDataset, dataset_id)
    if dataset is None or dataset.status != "ready":
        raise ValueError("Dataset not ready for publication")

    # Lock and supersede current published
    current = session.scalar(
        select(AARankingDataset).where(
            AARankingDataset.dataset_key == dataset.dataset_key,
            AARankingDataset.status == "published",
        ).with_for_update()
    )
    if current is not None:
        current.status = "superseded"

    dataset.status = "published"
    dataset.published_at = datetime.utcnow()
    session.flush()
    return dataset


def _serialize_entry(entry: AARankingEntry) -> dict:
    return {
        "id": entry.id,
        "rank": entry.rank,
        "model": entry.model_name,
        "title": entry.model_name,
        "creator": entry.creator_name,
        "subtitle": entry.creator_name,
        "score": float(entry.score) if entry.score is not None else None,
        "score_type": entry.score_type,
        "ci_95": float(entry.ci_95) if entry.ci_95 is not None else None,
        "release_date": entry.release_date.isoformat() if entry.release_date else None,
        "metrics": entry.metrics_json or {},
    }


def get_published_ranking(
    session: Session,
    dataset_key: str,
    limit: int,
) -> tuple[list[dict], dict | None]:
    """Return ranked items and metadata for a published dataset."""
    dataset = session.scalar(
        select(AARankingDataset).where(
            AARankingDataset.dataset_key == dataset_key,
            AARankingDataset.status == "published",
        ).order_by(AARankingDataset.published_at.desc()).limit(1)
    )
    if dataset is None:
        return [], None

    entries = list(session.scalars(
        select(AARankingEntry)
        .where(AARankingEntry.dataset_id == dataset.id)
        .order_by(AARankingEntry.rank.is_(None), AARankingEntry.rank.asc())
        .limit(limit)
    ))

    is_stale = dataset.captured_at < datetime.utcnow() - timedelta(hours=settings.artificial_analysis_stale_hours)

    meta = {
        "dataset_key": dataset.dataset_key,
        "score_type": dataset.score_type,
        "captured_at": dataset.captured_at.isoformat() if dataset.captured_at else None,
        "source_name": "Artificial Analysis",
        "source_url": "https://artificialanalysis.ai/",
        "scope_note": (
            "中国模型范围由今日看点根据模型厂商归属整理，原始评分来自 Artificial Analysis。"
            if dataset.scope == "china" else None
        ),
        "is_stale": is_stale,
    }

    return [_serialize_entry(e) for e in entries], meta


def get_creator_coverage(session: Session) -> dict[str, int | float]:
    """Report creator classification coverage."""
    creators = list(session.scalars(select(AACreatorRegion)))
    total = len(creators)
    resolved_by_id = sum(1 for c in creators if c.region_code != "unknown" and c.creator_external_id)
    resolved_by_name = sum(1 for c in creators if c.region_code != "unknown" and not c.creator_external_id)
    unresolved = total - resolved_by_id - resolved_by_name

    # Entry coverage from latest published language_global
    classified_entry_percent = 0.0
    latest = session.scalar(
        select(AARankingDataset).where(
            AARankingDataset.dataset_key == "language_global",
            AARankingDataset.status == "published",
        ).order_by(AARankingDataset.published_at.desc()).limit(1)
    )
    if latest is not None:
        total_entries = session.scalar(
            select(AARankingEntry).where(AARankingEntry.dataset_id == latest.id)
        )
        if total_entries:
            total_entries_count = latest.entry_count
            classified = sum(
                1 for e in session.scalars(
                    select(AARankingEntry).where(
                        AARankingEntry.dataset_id == latest.id,
                        AARankingEntry.creator_region != "unknown",
                    )
                )
            )
            classified_entry_percent = round(classified * 100 / total_entries_count, 2) if total_entries_count else 0.0

    return {
        "total_unique_creators": total,
        "resolved_by_id": resolved_by_id,
        "resolved_by_name": resolved_by_name,
        "unresolved": unresolved,
        "classified_entry_percent": classified_entry_percent,
    }


def mark_abandoned_runs(session: Session, *, older_than_minutes: int = 30) -> int:
    """Mark stale pending/running runs as abandoned."""
    cutoff = datetime.utcnow() - timedelta(minutes=older_than_minutes)
    count = 0
    runs = session.scalars(
        select(AASyncRun).where(
            AASyncRun.status.in_(["pending", "running"]),
            AASyncRun.heartbeat_at < cutoff,
        )
    ).all()
    for run in runs:
        run.status = "abandoned"
        count += 1
    session.flush()
    return count


def cleanup_artificial_analysis_history(session: Session, *, now: datetime | None = None) -> dict[str, int]:
    """Remove expired records per retention policy."""
    now = now or datetime.utcnow()
    result = {"sync_runs": 0, "raw_snapshots": 0, "datasets": 0, "entries": 0}

    # Keep published datasets indefinitely. Superseded: 180 days. Failed: 30 days.
    old_failed = session.scalars(
        select(AARankingDataset).where(
            AARankingDataset.status.in_(["failed", "parsing"]),
            AARankingDataset.created_at < now - timedelta(days=30),
        )
    ).all()
    for ds in old_failed:
        session.execute(text("DELETE FROM aa_ranking_entries WHERE dataset_id = :did"), {"did": ds.id})
        session.delete(ds)
        result["entries"] += 1
        result["datasets"] += 1

    old_superseded = session.scalars(
        select(AARankingDataset).where(
            AARankingDataset.status == "superseded",
            AARankingDataset.created_at < now - timedelta(days=180),
        )
    ).all()
    for ds in old_superseded:
        session.execute(text("DELETE FROM aa_ranking_entries WHERE dataset_id = :did"), {"did": ds.id})
        session.delete(ds)
        result["entries"] += 1
        result["datasets"] += 1

    # Snapshots: 90 days unless referenced
    old_snaps = session.scalars(
        select(AARawSnapshot).where(
            AARawSnapshot.captured_at < now - timedelta(days=90),
        )
    ).all()
    for snap in old_snaps:
        session.delete(snap)
        result["raw_snapshots"] += 1

    # Runs: 180 days
    old_runs = session.scalars(
        select(AASyncRun).where(
            AASyncRun.created_at < now - timedelta(days=180),
        )
    ).all()
    for run in old_runs:
        session.delete(run)
        result["sync_runs"] += 1

    session.flush()
    return result
