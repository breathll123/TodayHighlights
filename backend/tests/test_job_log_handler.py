# -*- coding: utf-8 -*-
import logging
from datetime import datetime

from sqlalchemy import create_engine, delete, event
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.entities import CrawlJob, JobLogEntry, Source, Topic
from app.core.logging import JobLogHandler, bind_log_context, build_event_record


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


def _handler_for(engine):
    """
    辅助函数，创建一个绑定了测试数据库 engine 的 JobLogHandler 实例，并限制其 batch_size 为 1 以便于即时测试。
    """
    return JobLogHandler(session_factory=sessionmaker(bind=engine), batch_size=1)


def test_handler_persists_event_with_job_id():
    """
    测试 JobLogHandler 当日志上下文携带 crawl_job_id 时是否能正确将日志事件写入数据库。
    """
    eng = _engine()
    with sessionmaker(bind=eng)() as s:
        job = _seed_job(s)
        job_id = job.id
    handler = _handler_for(eng)
    with bind_log_context(crawl_job_id=job_id):
        rec = build_event_record(logging.INFO, channel="application", category="crawler",
                                 event="crawl.fetch.completed", stage="fetch", found=5)
    handler.emit(rec)
    handler.flush()
    with sessionmaker(bind=eng)() as s:
        rows = s.query(JobLogEntry).all()
        assert len(rows) == 1
        assert rows[0].event == "crawl.fetch.completed"
        assert rows[0].stage == "fetch"
        assert rows[0].message == "抓取获取完成"          # 对齐 event_spec 描述映射
        assert rows[0].fields_json["found"] == 5


def test_handler_skips_event_without_job_id():
    """
    测试 JobLogHandler 是否会自动忽略没有绑定 crawl_job_id 的普通应用日志。
    """
    eng = _engine()
    handler = _handler_for(eng)
    rec = build_event_record(logging.INFO, channel="application", event="app.started")
    handler.emit(rec)
    handler.flush()
    with sessionmaker(bind=eng)() as s:
        assert s.query(JobLogEntry).count() == 0


def test_handler_force_flushes_terminal_event():
    """
    测试当触发终态事件（以 .completed 或 .failed 结尾的事件）或错误警告日志级别时，
    JobLogHandler 应该立即将缓存强刷入库，无须等待批量数量或时间间隔。
    """
    eng = _engine()
    with sessionmaker(bind=eng)() as s:
        job_id = _seed_job(s).id
    # 设置一个非常大的 batch_size，从而测试强刷触发行为
    handler = JobLogHandler(session_factory=sessionmaker(bind=eng), batch_size=999)
    with bind_log_context(crawl_job_id=job_id):
        rec = build_event_record(logging.INFO, channel="application", category="crawler",
                                 event="crawl.completed", status="success")
    handler.emit(rec)  # 终态事件应立即强刷落库，无须显式调用 flush()
    with sessionmaker(bind=eng)() as s:
        assert s.query(JobLogEntry).count() == 1
