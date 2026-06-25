"""Stop a stuck job + reconcile orphaned 'running' jobs on startup.

Root cause these guard against: run_crawl_job refuses to start a new job while
one is status='running' for the source. A process restart/hang leaves a zombie
'running' row that permanently blocks the source. stop_job releases it on
demand; reconcile_stale_jobs clears all orphans at startup.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import CrawlJob, Source, Topic
from app.services.jobs import reconcile_stale_jobs, stop_job


def _seed_job(db: Session, status: str = "running") -> int:
    topic = Topic(name="AI", slug="ai")
    db.add(topic)
    db.flush()
    source = Source(topic_id=topic.id, site="github_skills", name="GitHub-Skills",
                    entry_url="github_skills://ranking")
    db.add(source)
    db.flush()
    job = CrawlJob(source_id=source.id, trigger_type="manual", status=status)
    db.add(job)
    db.commit()
    return job.id


def test_stop_job_marks_running_as_stopped(db_session: Session):
    job_id = _seed_job(db_session, status="running")
    job = stop_job(db_session, job_id)
    assert job.status == "stopped"
    assert job.finished_at is not None
    # Running guard released: no more 'running' rows.
    assert db_session.scalar(select(CrawlJob).where(CrawlJob.status == "running")) is None


def test_stop_job_idempotent_on_finished(db_session: Session):
    job_id = _seed_job(db_session, status="success")
    job = stop_job(db_session, job_id)
    assert job.status == "success"  # already finished → untouched


def test_stop_job_missing_raises(db_session: Session):
    with pytest.raises(ValueError):
        stop_job(db_session, 999999)


def test_reconcile_stale_jobs_fails_orphans_only(db_session: Session):
    running_id = _seed_job(db_session, status="running")
    src = db_session.scalar(select(Source))
    db_session.add(CrawlJob(source_id=src.id, trigger_type="manual", status="success"))
    db_session.commit()

    count = reconcile_stale_jobs(db_session)

    assert count == 1
    refreshed = db_session.get(CrawlJob, running_id)
    assert refreshed.status == "failed"
    assert refreshed.finished_at is not None
    # The already-successful job is untouched.
    successes = db_session.scalars(select(CrawlJob).where(CrawlJob.status == "success")).all()
    assert len(successes) == 1


def test_stop_job_endpoint(client: TestClient, db_session: Session):
    job_id = _seed_job(db_session, status="running")
    resp = client.post(f"/api/admin/jobs/{job_id}/stop")
    assert resp.status_code == 200
    assert resp.json()["status"] == "stopped"


def test_stop_job_endpoint_404(client: TestClient):
    resp = client.post("/api/admin/jobs/999999/stop")
    assert resp.status_code == 404


def test_list_jobs_status_filter(client: TestClient, db_session: Session):
    topic = Topic(name="AI", slug="ai")
    db_session.add(topic)
    db_session.flush()
    source = Source(topic_id=topic.id, site="github_skills", name="GH", entry_url="x")
    db_session.add(source)
    db_session.flush()
    for s in ["success", "success", "failed", "running"]:
        db_session.add(CrawlJob(source_id=source.id, trigger_type="manual", status=s))
    db_session.commit()

    allr = client.get("/api/admin/jobs").json()
    assert allr["total"] == 4

    failed = client.get("/api/admin/jobs", params={"status": "failed"}).json()
    assert failed["total"] == 1
    assert all(it["status"] == "failed" for it in failed["items"])
    # Stats card stays the overall distribution, unaffected by the row filter.
    assert failed["stats"]["success"] == 2
    assert failed["stats"]["failed"] == 1
    assert failed["stats"]["running"] == 1

    # "all" behaves like no filter.
    assert client.get("/api/admin/jobs", params={"status": "all"}).json()["total"] == 4
