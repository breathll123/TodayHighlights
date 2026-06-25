# -*- coding: utf-8 -*-
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.entities import CrawlJob, JobLogEntry, Source, Topic


def _seed(db: Session, status: str = "running") -> int:
    """
    辅助函数：向数据库填充测试用的 CrawlJob 任务记录及多条关联的 JobLogEntry 结构化日志。
    """
    topic = Topic(name="股票", slug="stocks")
    db.add(topic)
    db.flush()
    source = Source(topic_id=topic.id, site="xueqiu", name="雪球", entry_url="u")
    db.add(source)
    db.flush()
    job = CrawlJob(source_id=source.id, trigger_type="manual", status=status,
                   items_found=3, items_saved=2)
    db.add(job)
    db.flush()
    # 模拟向此任务写入三条测试日志
    for i, ev in enumerate(["crawl.started", "crawl.fetch.completed", "crawl.completed"]):
        db.add(JobLogEntry(crawl_job_id=job.id, ts=datetime(2026, 6, 25, 10, i),
                           level="INFO", channel="application", event=ev,
                           category="crawler", stage="fetch", message=ev, fields_json={"i": i}))
    db.commit()
    return job.id


def test_get_job_logs_returns_timeline(client: TestClient, db_session: Session):
    """
    测试获取指定任务的全部日志时间线，确保返回正确的 JSON 结构以及 done 等控制属性。
    """
    job_id = _seed(db_session, status="success")
    resp = client.get(f"/api/admin/jobs/{job_id}/logs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["job"]["id"] == job_id
    assert body["done"] is True
    assert len(body["entries"]) == 3
    assert body["entries"][0]["event"] == "crawl.started"
    assert body["latest_id"] == body["entries"][-1]["id"]


def test_get_job_logs_incremental_after_id(client: TestClient, db_session: Session):
    """
    测试通过 after_id 参数增量获取日志的功能，用于实现 Live Tail 轮询。
    """
    job_id = _seed(db_session, status="running")
    full = client.get(f"/api/admin/jobs/{job_id}/logs").json()
    first_id = full["entries"][0]["id"]
    # 仅请求大于第一条日志 ID 的后续日志
    resp = client.get(f"/api/admin/jobs/{job_id}/logs", params={"after_id": first_id})
    body = resp.json()
    assert len(body["entries"]) == 2
    assert all(e["id"] > first_id for e in body["entries"])
    assert body["done"] is False


def test_get_job_logs_404_for_missing_job(client: TestClient):
    """
    测试当请求不存在的任务 ID 日志时，应当返回 404 错误。
    """
    resp = client.get("/api/admin/jobs/999999/logs")
    assert resp.status_code == 404
