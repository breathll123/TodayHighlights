# -*- coding: utf-8 -*-
from datetime import datetime

from sqlalchemy import create_engine, delete, event
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.entities import CrawlJob, JobLogEntry, Source, Topic


def _engine(foreign_keys: bool = False):
    """
    创建内存 SQLite engine 并视情况启用外键约束，
    SQLite 需要手动执行 PRAGMA foreign_keys=ON 才会激活外键级联删除。
    """
    eng = create_engine("sqlite+pysqlite:///:memory:")
    if foreign_keys:
        @event.listens_for(eng, "connect")
        def _fk_on(dbapi_con, _):
            dbapi_con.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(eng)
    return eng


def _seed_job(session) -> CrawlJob:
    """
    初始化数据源、主题以及关联的爬取任务，并保存提交到数据库中。
    """
    topic = Topic(name="股票", slug="stocks")
    session.add(topic)
    session.flush()
    source = Source(topic_id=topic.id, site="xueqiu", name="雪球", entry_url="u")
    session.add(source)
    session.flush()
    job = CrawlJob(source_id=source.id, trigger_type="manual", status="running")
    session.add(job)
    session.commit()
    return job


def test_job_log_entry_persists():
    """
    测试 JobLogEntry 日志模型字段的持久化及正确读取，确保 JSON 类型的字段也能被正常反序列化。
    """
    Session = sessionmaker(bind=_engine())
    with Session() as s:
        job = _seed_job(s)
        s.add(JobLogEntry(
            crawl_job_id=job.id, ts=datetime(2026, 6, 25, 10, 0, 0),
            level="INFO", channel="application", event="crawl.started",
            category="crawler", stage="fetch", message="抓取任务开始",
            fields_json={"site": "xueqiu", "crawl_job_id": job.id},
        ))
        s.commit()
        row = s.query(JobLogEntry).one()
        assert row.event == "crawl.started"
        assert row.fields_json["site"] == "xueqiu"


def test_job_logs_cascade_delete_with_job():
    """
    测试当 CrawlJob 被删除时，级联删除对应的 JobLogEntry（基于物理外键 ON DELETE CASCADE 触发）。
    """
    Session = sessionmaker(bind=_engine(foreign_keys=True))
    with Session() as s:
        job = _seed_job(s)
        s.add(JobLogEntry(crawl_job_id=job.id, ts=datetime(2026, 6, 25), event="x",
                          message="m", fields_json={}))
        s.commit()
        # 清理工作，使用 bulk delete 动作，验证数据库底层级联是否成功工作
        s.execute(delete(CrawlJob).where(CrawlJob.id == job.id))
        s.commit()
        assert s.query(JobLogEntry).count() == 0
