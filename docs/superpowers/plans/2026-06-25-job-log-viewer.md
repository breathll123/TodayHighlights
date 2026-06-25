# 任务日志查看器 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给后台【任务】页每行加「日志」入口，点击后居中弹出该 CrawlJob 的结构化日志时间线（阶段进度 + 每个 HTTP 请求 + AI 子步骤 + 失败详情），运行中可实时 live tail。

**Architecture:** 新增 `job_log_entries` 表。日志系统在现有 `QueueListener` 上挂一个 `JobLogHandler`：凡带 `crawl_job_id` 的结构化事件，除了写文件外再落一份到该表（后台 listener 线程、独立 session、复用现有脱敏，零改业务代码）。新增 `GET /admin/jobs/{id}/logs?after_id=` 增量接口；前端用复用的 `Dialog` 弹出 `JobLogModal`，运行中每 2s 增量轮询。

**Tech Stack:** FastAPI + SQLAlchemy 2.0 + Alembic（短 revision id）；React 18 + Vite + TS + Tailwind + shadcn `Dialog` + react-query；后端测试 SQLite 内存，前端 vitest（node18）。

## Global Constraints

- 最高规格实现，每个功能有清晰边界、可测试、配套测试齐全（CLAUDE.md 质量约束）。
- Alembic revision **短格式**：新迁移 `revision = "0015"`，`down_revision = "0014"`（当前 head 是 0014）。
- MySQL **TEXT 列不得用 `server_default`**；用 Python 端 `default=""`。
- 主键用 `BIGINT_PK = BigInteger().with_variant(Integer, "sqlite")`。
- **每个 `event="..."` 字面量必须在 `app/core/logging_catalog.py` 的 `_EVENT_DESCRIPTIONS` 注册**，否则 `tests/test_logging_readability.py::test_all_literal_application_events_are_registered` 失败。
- AI 日志只记模型/任务/规模/Token/耗时，**不记 Prompt**。
- 日志落库为诊断用途，**绝不**因写失败影响任务事务或文件日志（独立 session + 静默降级，对齐 MediaCacheService 会话隔离铁律）。
- 后端测试命令：`APP_SECRET_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= REDIS_ENABLED=false python3 -m pytest tests/ -v`
- 前端命令需 node18：`PATH="/Users/lws/.nvm/versions/node/v18.20.4/bin:$PATH" npx vitest run` / `... npm run build`。
- 提交信息结尾加 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`。

---

## File Structure

| 文件 | 职责 |
|---|---|
| `backend/app/models/entities.py` (修改) | 新增 `JobLogEntry` 模型 + `CrawlJob.logs` 关系 |
| `backend/migrations/versions/20260625_0015_job_log_entries.py` (新建) | 建 `job_log_entries` 表（FK ON DELETE CASCADE） |
| `backend/app/core/logging.py` (修改) | 新增 `JobLogHandler`；接入 `LoggingRuntime.start/stop` |
| `backend/app/core/logging_catalog.py` (修改) | 注册 `skills.classify.batch` / `skills.translate.batch` |
| `backend/app/services/skills/classify.py` (修改) | classify/translate 每批发 `*.batch` 事件 |
| `backend/app/api/admin.py` (修改) | 新增 `GET /jobs/{job_id}/logs` |
| `backend/tests/conftest.py` (修改) | 抽出共享 `engine` fixture，新增 `db_session` |
| `backend/tests/test_job_log_handler.py` (新建) | handler 单测 |
| `backend/tests/test_job_logs_api.py` (新建) | 接口单测 |
| `backend/tests/test_skills_classify_events.py` (新建) | AI 子步骤事件单测 |
| `frontend/src/api/types.ts` (修改) | `JobLogEntry` / `JobLogResponse` 类型 |
| `frontend/src/api/client.ts` (修改) | `fetchJobLogs` |
| `frontend/src/components/admin/JobLogModal.tsx` (新建) | 居中模态时间线 |
| `frontend/src/pages/AdminJobsPage.tsx` (修改) | 每行「日志」按钮 + 挂载 modal；移除冗余的失败内联展开 |
| `frontend/src/__tests__/job-log-modal.test.tsx` (新建) | modal 渲染/展开测试 |
| `frontend/src/__tests__/admin-pages.test.tsx` (修改) | 补 `fetchJobLogs` mock + 断言「日志」按钮 |

---

## Task 1: `JobLogEntry` 模型 + 迁移 0015

**Files:**
- Modify: `backend/app/models/entities.py`（`CrawlJob` 类附近 + 文件末尾新增类）
- Create: `backend/migrations/versions/20260625_0015_job_log_entries.py`
- Test: `backend/tests/test_job_log_handler.py`（本任务先只放模型 + 级联测试）

**Interfaces:**
- Produces: `JobLogEntry(id, crawl_job_id, ts, level, channel, event, category, stage, message, fields_json, created_at)`；`CrawlJob.logs` 关系（`passive_deletes=True`）。

- [ ] **Step 1: 写失败测试（模型持久化 + 级联删除）**

Create `backend/tests/test_job_log_handler.py`:

```python
from datetime import datetime

from sqlalchemy import create_engine, delete, event
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.entities import CrawlJob, JobLogEntry, Source, Topic


def _engine(foreign_keys: bool = False):
    eng = create_engine("sqlite+pysqlite:///:memory:")
    if foreign_keys:
        @event.listens_for(eng, "connect")
        def _fk_on(dbapi_con, _):  # SQLite enforces FK only when asked
            dbapi_con.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(eng)
    return eng


def _seed_job(session) -> CrawlJob:
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
    Session = sessionmaker(bind=_engine(foreign_keys=True))
    with Session() as s:
        job = _seed_job(s)
        s.add(JobLogEntry(crawl_job_id=job.id, ts=datetime(2026, 6, 25), event="x",
                          message="m", fields_json={}))
        s.commit()
        # Production cleanup uses bulk delete → relies on DB-level ON DELETE CASCADE.
        s.execute(delete(CrawlJob).where(CrawlJob.id == job.id))
        s.commit()
        assert s.query(JobLogEntry).count() == 0
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && APP_SECRET_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= REDIS_ENABLED=false python3 -m pytest tests/test_job_log_handler.py -v`
Expected: FAIL — `ImportError: cannot import name 'JobLogEntry'`.

- [ ] **Step 3: 在 `entities.py` 新增模型 + 关系**

在 `CrawlJob` 类内（`source` 关系那一行下面）追加：

```python
    logs: Mapped[list["JobLogEntry"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", passive_deletes=True
    )
```

在 `CrawlJob` 类之后新增类：

```python
class JobLogEntry(Base):
    __tablename__ = "job_log_entries"
    __table_args__ = (
        Index("ix_job_log_entries_job_id", "crawl_job_id", "id"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK, primary_key=True, autoincrement=True)
    crawl_job_id: Mapped[int] = mapped_column(
        ForeignKey("crawl_jobs.id", ondelete="CASCADE"), nullable=False
    )
    ts: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    level: Mapped[str] = mapped_column(String(10), default="INFO", nullable=False)
    channel: Mapped[str] = mapped_column(String(20), default="application", nullable=False)
    event: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    category: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    stage: Mapped[str] = mapped_column(String(30), default="", nullable=False)
    message: Mapped[str] = mapped_column(Text, default="", nullable=False)  # TEXT：不加 server_default
    fields_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    job: Mapped["CrawlJob"] = relationship(back_populates="logs")
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend && APP_SECRET_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= REDIS_ENABLED=false python3 -m pytest tests/test_job_log_handler.py -v`
Expected: PASS（2 passed）。

- [ ] **Step 5: 写 Alembic 迁移**

Create `backend/migrations/versions/20260625_0015_job_log_entries.py`:

```python
"""job log entries — per-job structured log timeline

Revision ID: 0015
Revises: 0014
Create Date: 2026-06-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "job_log_entries",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("crawl_job_id", sa.Integer(), nullable=False),
        sa.Column("ts", sa.DateTime(), nullable=False),
        sa.Column("level", sa.String(10), nullable=False, server_default="INFO"),
        sa.Column("channel", sa.String(20), nullable=False, server_default="application"),
        sa.Column("event", sa.String(80), nullable=False, server_default=""),
        sa.Column("category", sa.String(20), nullable=False, server_default=""),
        sa.Column("stage", sa.String(30), nullable=False, server_default=""),
        sa.Column("message", sa.Text(), nullable=False),  # TEXT：省略 server_default
        sa.Column("fields_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["crawl_job_id"], ["crawl_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_log_entries_job_id", "job_log_entries", ["crawl_job_id", "id"])


def downgrade() -> None:
    op.drop_index("ix_job_log_entries_job_id", table_name="job_log_entries")
    op.drop_table("job_log_entries")
```

- [ ] **Step 6: 校验迁移语法**

Run: `cd backend && python3 -m py_compile migrations/versions/20260625_0015_job_log_entries.py`
Expected: 无输出（成功）。

- [ ] **Step 7: 提交**

```bash
cd backend && git add app/models/entities.py migrations/versions/20260625_0015_job_log_entries.py tests/test_job_log_handler.py
git commit -m "feat(jobs): JobLogEntry 模型 + 迁移 0015（按任务日志时间线，FK 级联）

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: `JobLogHandler` 日志落库器

**Files:**
- Modify: `backend/app/core/logging.py`（新增 `JobLogHandler` 类，放在 `log_adapter_failure` 之后、`LoggingConfig` 之前）
- Test: `backend/tests/test_job_log_handler.py`（追加 handler 行为测试）

**Interfaces:**
- Consumes: `build_event_record(...)`（已存在）产生的 `LogRecord`，其 `event_fields`/`event`/`log_channel` 属性。
- Produces: `JobLogHandler(session_factory=None, *, batch_size=50, flush_interval=0.25)`，方法 `emit(record)`、`flush()`。

- [ ] **Step 1: 追加失败测试**

在 `backend/tests/test_job_log_handler.py` 顶部 import 补充：

```python
import logging

from app.core.logging import JobLogHandler, bind_log_context, build_event_record
```

追加测试函数：

```python
def _handler_for(engine):
    return JobLogHandler(session_factory=sessionmaker(bind=engine), batch_size=1)


def test_handler_persists_event_with_job_id():
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
        assert rows[0].message == "抓取获取完成"          # event_spec 描述
        assert rows[0].fields_json["found"] == 5


def test_handler_skips_event_without_job_id():
    eng = _engine()
    handler = _handler_for(eng)
    rec = build_event_record(logging.INFO, channel="application", event="app.started")
    handler.emit(rec)
    handler.flush()
    with sessionmaker(bind=eng)() as s:
        assert s.query(JobLogEntry).count() == 0


def test_handler_force_flushes_terminal_event():
    eng = _engine()
    with sessionmaker(bind=eng)() as s:
        job_id = _seed_job(s).id
    handler = JobLogHandler(session_factory=sessionmaker(bind=eng), batch_size=999)  # 大 batch，不靠条数触发
    with bind_log_context(crawl_job_id=job_id):
        rec = build_event_record(logging.INFO, channel="application", category="crawler",
                                 event="crawl.completed", status="success")
    handler.emit(rec)  # 终态事件应立即 flush，无需手动 flush()
    with sessionmaker(bind=eng)() as s:
        assert s.query(JobLogEntry).count() == 1
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && APP_SECRET_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= REDIS_ENABLED=false python3 -m pytest tests/test_job_log_handler.py -v`
Expected: FAIL — `ImportError: cannot import name 'JobLogHandler'`.

- [ ] **Step 3: 实现 `JobLogHandler`**

在 `backend/app/core/logging.py`，`log_adapter_failure` 函数之后新增（`datetime`、`SH_TZ`、`threading`、`time` 已在文件顶部 import）：

```python
class JobLogHandler(logging.Handler):
    """把带 crawl_job_id 的结构化事件落到 job_log_entries（后台【任务】页时间线）。

    运行在 QueueListener 线程；每次 flush 用独立短会话，写失败静默丢弃，绝不影响
    任务事务或文件日志（对齐 MediaCacheService 会话隔离铁律）。批量降低高频 HTTP 源写压。
    """

    _TERMINAL_SUFFIXES = (".completed", ".failed")

    def __init__(self, session_factory=None, *, batch_size: int = 50, flush_interval: float = 0.25):
        super().__init__()
        self._session_factory = session_factory
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._buffer: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._last_flush = time.monotonic()

    def _factory(self):
        if self._session_factory is not None:
            return self._session_factory
        from app.core.database import SessionLocal
        return SessionLocal

    def emit(self, record: logging.LogRecord) -> None:
        try:
            fields = dict(getattr(record, "event_fields", {}) or {})
            job_id = fields.get("crawl_job_id")
            if job_id is None:
                return
            from app.core.logging_catalog import event_spec
            event = (getattr(record, "event", "") or record.getMessage())[:80]
            row = {
                "crawl_job_id": int(job_id),
                "ts": datetime.fromtimestamp(record.created, tz=SH_TZ).replace(tzinfo=None),
                "level": record.levelname,
                "channel": getattr(record, "log_channel", "application"),
                "event": event,
                "category": str(fields.get("category", ""))[:20],
                "stage": str(fields.get("stage", ""))[:30],
                "message": event_spec(event).description,
                "fields_json": fields,
            }
            terminal = event.endswith(self._TERMINAL_SUFFIXES) or record.levelno >= logging.WARNING
            with self._lock:
                self._buffer.append(row)
                due = (
                    terminal
                    or len(self._buffer) >= self._batch_size
                    or (time.monotonic() - self._last_flush) >= self._flush_interval
                )
            if due:
                self.flush()
        except Exception:  # noqa: BLE001 — 日志绝不能反噬调用方
            pass

    def flush(self) -> None:
        with self._lock:
            rows, self._buffer = self._buffer, []
            self._last_flush = time.monotonic()
        if not rows:
            return
        from app.models.entities import JobLogEntry
        try:
            with self._factory()() as session:
                session.add_all([JobLogEntry(**r) for r in rows])
                session.commit()
        except Exception:  # noqa: BLE001 — 诊断日志，丢弃即可
            pass
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend && APP_SECRET_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= REDIS_ENABLED=false python3 -m pytest tests/test_job_log_handler.py -v`
Expected: PASS（5 passed）。

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/core/logging.py tests/test_job_log_handler.py
git commit -m "feat(logging): JobLogHandler — 带 crawl_job_id 的事件落库（独立会话、批量、终态强刷）

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: 把 `JobLogHandler` 接入 `LoggingRuntime`

**Files:**
- Modify: `backend/app/core/logging.py`（`LoggingRuntime.__init__` / `start` / `stop`）

**Interfaces:**
- Consumes: `JobLogHandler`（Task 2）。
- Produces: `LoggingRuntime.job_log_handler` 字段；listener targets 含该 handler。

> 说明：此任务是把 handler 挂到运行时管线。无独立单测（其行为已在 Task 2 覆盖；接入正确性由 Task 9 全量回归保证——所有现有测试在 lifespan 启动后仍须绿）。属于 Task 2 的配置收尾，但单独提交便于回滚。

- [ ] **Step 1: `__init__` 增加字段**

在 `LoggingRuntime.__init__` 末尾（`self._saved_library_levels = {}` 之后）加：

```python
        self.job_log_handler: JobLogHandler | None = None
```

- [ ] **Step 2: `start()` 构建 handler 并加入 targets**

在 `start()` 里、`# Queue + listener` 注释之前插入：

```python
        # DB sink：把带 crawl_job_id 的事件落库，供后台【任务】页时间线。
        # 尽力而为——内部 flush 异常自吞，绝不影响文件日志。
        self.job_log_handler = JobLogHandler()
        self.job_log_handler.setLevel(self.config.level)
```

在 `targets: list[logging.Handler] = []` 之后、构建 `queue_handler` 之前，把它加入 targets：

```python
        if self.job_log_handler is not None:
            targets.append(self.job_log_handler)
```

（放在 `if self.console_handler: targets.append(self.console_handler)` 之后即可。）

- [ ] **Step 3: `stop()` 收尾 flush**

在 `stop()` 内 `if self.listener: self.listener.stop()` 之后加：

```python
        if self.job_log_handler is not None:
            try:
                self.job_log_handler.flush()
            except Exception:
                pass
```

- [ ] **Step 4: 语法校验 + 现有日志测试回归**

Run: `cd backend && APP_SECRET_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= REDIS_ENABLED=false python3 -m pytest tests/test_logging_readability.py tests/test_job_log_handler.py -v`
Expected: PASS（全绿；接入后日志管线仍正常）。

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/core/logging.py
git commit -m "feat(logging): LoggingRuntime 挂载 JobLogHandler 到 listener targets

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: skills 分类/翻译每批发 `*.batch` 事件 + 注册事件目录

**Files:**
- Modify: `backend/app/services/skills/classify.py`
- Modify: `backend/app/core/logging_catalog.py`（注册新事件）
- Test: `backend/tests/test_skills_classify_events.py`（新建）

**Interfaces:**
- Produces: 事件 `skills.classify.batch`（fields: model, batch, size, duration）、`skills.translate.batch`（同）。

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_skills_classify_events.py`:

```python
import asyncio
import logging
from datetime import datetime

from app.services.skills.classify import classify_skills, translate_skills
from app.models.entities import Skill


class _FakeClient:
    model_name = "fake-model"

    async def complete_json(self, prompt: str, content: str) -> dict:
        import json
        items = json.loads(content)
        return {"results": [{"full_name": i["full_name"], "label": "skill",
                             "reason": "ok", "zh": "中文描述"} for i in items]}


def _skill(name: str) -> Skill:
    return Skill(source="github", external_id=name, name=name, url="u",
                 description="An English skill description", extra_json={"full_name": name})


def test_classify_emits_batch_event(caplog):
    skills = [_skill("a"), _skill("b")]
    with caplog.at_level(logging.INFO, logger="today_highlights.skills"):
        asyncio.run(classify_skills(_FakeClient(), skills, "p", "v1", batch_size=10,
                                    now=datetime(2026, 6, 25)))
    events = [getattr(r, "event", None) for r in caplog.records]
    assert "skills.classify.batch" in events
    assert all(s.is_skill for s in skills)


def test_translate_emits_batch_event(caplog):
    skills = [_skill("a")]
    skills[0].is_skill = True
    with caplog.at_level(logging.INFO, logger="today_highlights.skills"):
        asyncio.run(translate_skills(_FakeClient(), skills, "p", batch_size=10,
                                     now=datetime(2026, 6, 25)))
    events = [getattr(r, "event", None) for r in caplog.records]
    assert "skills.translate.batch" in events
    assert skills[0].description_zh == "中文描述"
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && APP_SECRET_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= REDIS_ENABLED=false python3 -m pytest tests/test_skills_classify_events.py -v`
Expected: FAIL — `assert "skills.classify.batch" in events` 不成立（事件未发）。

- [ ] **Step 3: classify.py 发事件**

在 `classify.py` 顶部 import 区补：

```python
import time

from app.core.logging import format_duration, log_event
```

（`log_event` 已 import，只需新增 `time` 与 `format_duration`。）

`classify_skills` 的循环改为带计时与成功事件：

```python
    for idx, batch in enumerate(_chunked(skills, batch_size), 1):
        started = time.perf_counter()
        payload = [
            {"full_name": skill_key(s), "description": s.description, "topics": (s.extra_json or {}).get("topics", [])}
            for s in batch
        ]
        try:
            result = await client.complete_json(prompt, json.dumps(payload, ensure_ascii=False))
        except Exception as exc:  # noqa: BLE001 — log + skip batch, keep syncing
            log_event(logger, channel="application", category="ai", event="skills.classify.failed",
                      level=logging.ERROR, error_type=type(exc).__name__, error=str(exc), batch_size=len(batch))
            continue
        verdicts = {v.get("full_name"): v for v in result.get("results", [])}
        for s in batch:
            v = verdicts.get(skill_key(s))
            if not v:
                continue
            label = v.get("label") if v.get("label") in _VALID_LABELS else "unrelated"
            s.skill_kind = label
            s.is_skill = label == "skill"
            s.classify_reason = (v.get("reason") or "")[:120]
            s.classify_prompt_version = prompt_version
            s.classified_by_model = model
            s.classified_at = now
        log_event(logger, channel="application", category="ai", event="skills.classify.batch",
                  model=model, batch=idx, size=len(batch),
                  duration=format_duration(time.perf_counter() - started))
```

`translate_skills` 的批循环同样在成功应用译文后补：

```python
    for idx, batch in enumerate(_chunked(pending, batch_size), 1):
        started = time.perf_counter()
        payload = [{"full_name": skill_key(s), "description": s.description} for s in batch]
        try:
            result = await client.complete_json(prompt, json.dumps(payload, ensure_ascii=False))
        except Exception as exc:  # noqa: BLE001
            log_event(logger, channel="application", category="ai", event="skills.translate.failed",
                      level=logging.ERROR, error_type=type(exc).__name__, error=str(exc), batch_size=len(batch))
            continue
        zh_by_key = {v.get("full_name"): (v.get("zh") or "").strip() for v in result.get("results", [])}
        for s in batch:
            zh = zh_by_key.get(skill_key(s))
            if zh:
                s.description_zh = zh
                s.translated_by_model = model
                s.translated_at = now
        log_event(logger, channel="application", category="ai", event="skills.translate.batch",
                  model=model, batch=idx, size=len(batch),
                  duration=format_duration(time.perf_counter() - started))
```

- [ ] **Step 4: 注册事件目录**

在 `backend/app/core/logging_catalog.py` 的 `_EVENT_DESCRIPTIONS` 字典里，`"skills.classify.failed"` 之前/之后按字母序插入：

```python
    "skills.classify.batch": "技能分类批次完成",
```

并在 `"skills.translate.failed"` 之前插入：

```python
    "skills.translate.batch": "技能翻译批次完成",
```

- [ ] **Step 5: 运行测试，确认通过（含目录覆盖测试）**

Run: `cd backend && APP_SECRET_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= REDIS_ENABLED=false python3 -m pytest tests/test_skills_classify_events.py tests/test_logging_readability.py -v`
Expected: PASS（新事件已发且已注册，`test_all_literal_application_events_are_registered` 仍绿）。

- [ ] **Step 6: 提交**

```bash
cd backend && git add app/services/skills/classify.py app/core/logging_catalog.py tests/test_skills_classify_events.py
git commit -m "feat(skills): 分类/翻译每批发 *.batch 事件并注册到事件目录

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: `GET /admin/jobs/{job_id}/logs` 接口 + 共享测试 fixture

**Files:**
- Modify: `backend/tests/conftest.py`（抽 `engine` fixture + 新增 `db_session`）
- Modify: `backend/app/api/admin.py`（import `JobLogEntry`；新增端点，紧跟 `list_jobs` 之后）
- Test: `backend/tests/test_job_logs_api.py`（新建）

**Interfaces:**
- Consumes: `JobLogEntry`、`CrawlJob`、`verify_admin`（测试中已被 override 为 True）。
- Produces: `GET /api/admin/jobs/{job_id}/logs?after_id=<int>` → `{job, entries, latest_id, done}`；`db_session` fixture（与 `client` 共享同一 engine）。

- [ ] **Step 1: 重构 conftest 暴露共享 engine + db_session**

把 `backend/tests/conftest.py` 的 `client` fixture 改为依赖一个新的 `engine` fixture，并新增 `db_session`。替换 `client` fixture 及其上方，为：

```python
@pytest.fixture
def engine():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    yield eng


@pytest.fixture
def db_session(engine) -> Generator:
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(engine) -> Generator[TestClient, None, None]:
    app.dependency_overrides.clear()

    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_session():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    def override_verify_admin():
        return True

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[verify_admin] = override_verify_admin

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
```

（注意：删掉原 `client` 里自建 `engine = create_engine(...)` 与 `Base.metadata.create_all(engine)` 两行——现由 `engine` fixture 提供。其余 import 不变。）

- [ ] **Step 2: 写失败测试**

Create `backend/tests/test_job_logs_api.py`:

```python
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.entities import CrawlJob, JobLogEntry, Source, Topic


def _seed(db: Session, status: str = "running") -> int:
    topic = Topic(name="股票", slug="stocks")
    db.add(topic); db.flush()
    source = Source(topic_id=topic.id, site="xueqiu", name="雪球", entry_url="u")
    db.add(source); db.flush()
    job = CrawlJob(source_id=source.id, trigger_type="manual", status=status,
                   items_found=3, items_saved=2)
    db.add(job); db.flush()
    for i, ev in enumerate(["crawl.started", "crawl.fetch.completed", "crawl.completed"]):
        db.add(JobLogEntry(crawl_job_id=job.id, ts=datetime(2026, 6, 25, 10, i),
                           level="INFO", channel="application", event=ev,
                           category="crawler", stage="fetch", message=ev, fields_json={"i": i}))
    db.commit()
    return job.id


def test_get_job_logs_returns_timeline(client: TestClient, db_session: Session):
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
    job_id = _seed(db_session, status="running")
    full = client.get(f"/api/admin/jobs/{job_id}/logs").json()
    first_id = full["entries"][0]["id"]
    resp = client.get(f"/api/admin/jobs/{job_id}/logs", params={"after_id": first_id})
    body = resp.json()
    assert len(body["entries"]) == 2
    assert all(e["id"] > first_id for e in body["entries"])
    assert body["done"] is False


def test_get_job_logs_404_for_missing_job(client: TestClient):
    resp = client.get("/api/admin/jobs/999999/logs")
    assert resp.status_code == 404
```

- [ ] **Step 3: 运行测试，确认失败**

Run: `cd backend && APP_SECRET_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= REDIS_ENABLED=false python3 -m pytest tests/test_job_logs_api.py -v`
Expected: FAIL — 404/路由不存在（端点未实现）。

- [ ] **Step 4: 实现端点**

`backend/app/api/admin.py`：在第 13 行的实体 import 里加入 `JobLogEntry`：

```python
from app.models.entities import AIGenerationJob, AIBlockAnalysis, AIPromptTemplate, AITokenUsage, CrawlJob, Highlight, JobLogEntry, PageBlock, Source, Topic, User
```

在 `list_jobs` 函数之后新增：

```python
@router.get("/jobs/{job_id}/logs")
def get_job_logs(job_id: int, after_id: int = 0, session: Session = Depends(get_session)) -> dict:
    job = session.get(CrawlJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    rows = session.scalars(
        select(JobLogEntry)
        .where(JobLogEntry.crawl_job_id == job_id, JobLogEntry.id > after_id)
        .order_by(JobLogEntry.id.asc())
    ).all()
    latest_id = rows[-1].id if rows else after_id
    return {
        "job": {
            "id": job.id,
            "status": job.status,
            "started_at": job.started_at,
            "finished_at": job.finished_at,
            "items_found": job.items_found,
            "items_saved": job.items_saved,
            "error_message": job.error_message,
        },
        "entries": [
            {
                "id": e.id,
                "ts": e.ts,
                "level": e.level,
                "event": e.event,
                "category": e.category,
                "stage": e.stage,
                "message": e.message,
                "fields": e.fields_json,
            }
            for e in rows
        ],
        "latest_id": latest_id,
        "done": job.status in ("success", "failed"),
    }
```

- [ ] **Step 5: 运行测试，确认通过**

Run: `cd backend && APP_SECRET_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= REDIS_ENABLED=false python3 -m pytest tests/test_job_logs_api.py -v`
Expected: PASS（3 passed）。

- [ ] **Step 6: 全量后端回归（确认 conftest 改动不破坏其他测试）**

Run: `cd backend && APP_SECRET_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= REDIS_ENABLED=false python3 -m pytest tests/ -q`
Expected: 全绿。

- [ ] **Step 7: 提交**

```bash
cd backend && git add app/api/admin.py tests/conftest.py tests/test_job_logs_api.py
git commit -m "feat(api): GET /jobs/{id}/logs 任务日志时间线（增量 after_id）+ 共享测试 fixture

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: 前端 API client + 类型

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/client.ts`

**Interfaces:**
- Produces: 类型 `JobLogEntry` / `JobLogResponse`；函数 `fetchJobLogs(jobId: number, afterId?: number): Promise<JobLogResponse>`。

- [ ] **Step 1: 加类型**

在 `frontend/src/api/types.ts` 的 `JobListResponse` 定义之后新增：

```typescript
export interface JobLogEntry {
  id: number;
  ts: string;
  level: string;
  event: string;
  category: string;
  stage: string;
  message: string;
  fields: Record<string, unknown>;
}

export interface JobLogResponse {
  job: {
    id: number;
    status: string;
    started_at: string | null;
    finished_at: string | null;
    items_found: number;
    items_saved: number;
    error_message: string;
  };
  entries: JobLogEntry[];
  latest_id: number;
  done: boolean;
}
```

- [ ] **Step 2: 加 client 函数**

在 `frontend/src/api/client.ts` 第 2 行的类型 import 末尾补 `JobLogResponse`（加到 `JobListResponse,` 之后）。在 `fetchJobs` 之后新增：

```typescript
export function fetchJobLogs(jobId: number, afterId = 0): Promise<JobLogResponse> {
  return api
    .get<JobLogResponse>(`/api/admin/jobs/${jobId}/logs`, { params: { after_id: afterId } })
    .then((r) => r.data);
}
```

- [ ] **Step 3: 类型检查**

Run: `cd frontend && PATH="/Users/lws/.nvm/versions/node/v18.20.4/bin:$PATH" npx tsc --noEmit`
Expected: 无错误。

- [ ] **Step 4: 提交**

```bash
cd frontend && git add src/api/types.ts src/api/client.ts
git commit -m "feat(api-client): fetchJobLogs + JobLogResponse 类型

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: `JobLogModal` 居中模态时间线

**Files:**
- Create: `frontend/src/components/admin/JobLogModal.tsx`
- Test: `frontend/src/__tests__/job-log-modal.test.tsx`

**Interfaces:**
- Consumes: `fetchJobLogs`（Task 6）、`Dialog`/`DialogContent`/`DialogHeader`/`DialogTitle`（`@/components/ui/dialog`）、`Badge`。
- Produces: `JobLogModal({ jobId, open, onOpenChange })`，props 类型 `{ jobId: number | null; open: boolean; onOpenChange: (open: boolean) => void }`。

- [ ] **Step 1: 写失败测试**

Create `frontend/src/__tests__/job-log-modal.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { JobLogModal } from "@/components/admin/JobLogModal";

vi.mock("@/api/client", () => ({
  fetchJobLogs: vi.fn().mockResolvedValue({
    job: {
      id: 1, status: "failed",
      started_at: "2026-06-25T10:00:00", finished_at: "2026-06-25T10:01:00",
      items_found: 0, items_saved: 0, error_message: "Boom: connection refused",
    },
    entries: [
      { id: 1, ts: "2026-06-25T10:00:00", level: "INFO", event: "crawl.started",
        category: "crawler", stage: "fetch", message: "抓取任务开始", fields: {} },
      { id: 2, ts: "2026-06-25T10:00:01", level: "WARNING", event: "upstream.failed",
        category: "crawler", stage: "status", message: "上游请求失败",
        fields: { status: 403, url: "https://x.test/api", duration_ms: 12.3,
                  response_bytes: 88, response_preview: "forbidden" } },
      { id: 3, ts: "2026-06-25T10:00:02", level: "ERROR", event: "crawl.failed",
        category: "crawler", stage: "fetch", message: "抓取任务失败",
        fields: { error_type: "ConnectionError", error: "Boom: connection refused" } },
    ],
    latest_id: 3,
    done: true,
  }),
}));

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      {children}
    </QueryClientProvider>
  );
}

describe("JobLogModal", () => {
  it("renders the timeline, the failure block, and expands an HTTP row", async () => {
    render(<JobLogModal jobId={1} open onOpenChange={() => {}} />, { wrapper: Wrapper });

    expect(await screen.findByText("抓取任务开始")).toBeInTheDocument();
    expect(screen.getByText("上游请求失败")).toBeInTheDocument();
    // 失败概况块展示错误消息
    expect(screen.getByText(/connection refused/)).toBeInTheDocument();
    // HTTP 行展示状态码与脱敏 URL
    expect(screen.getByText(/403/)).toBeInTheDocument();
    expect(screen.getByText(/x\.test\/api/)).toBeInTheDocument();

    // 点击 HTTP 行展开，显示响应预览
    fireEvent.click(screen.getByText("上游请求失败"));
    await waitFor(() => expect(screen.getByText("forbidden")).toBeInTheDocument());
  });

  it("does not fetch when closed", () => {
    render(<JobLogModal jobId={1} open={false} onOpenChange={() => {}} />, { wrapper: Wrapper });
    expect(screen.queryByText("抓取任务开始")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd frontend && PATH="/Users/lws/.nvm/versions/node/v18.20.4/bin:$PATH" npx vitest run src/__tests__/job-log-modal.test.tsx`
Expected: FAIL — 模块不存在 `@/components/admin/JobLogModal`。

- [ ] **Step 3: 实现 `JobLogModal`**

Create `frontend/src/components/admin/JobLogModal.tsx`:

```tsx
import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { fetchJobLogs } from "@/api/client";
import type { JobLogEntry, JobLogResponse } from "@/api/types";
import { cn } from "@/lib/utils";

const levelClass: Record<string, string> = {
  ERROR: "text-red-500",
  WARNING: "text-amber-500",
  INFO: "text-muted-foreground",
};

function fmtClock(ts: string): string {
  const d = new Date(ts);
  return d.toLocaleTimeString();
}

function EntryRow({ entry }: { entry: JobLogEntry }) {
  const [open, setOpen] = useState(false);
  const f = entry.fields ?? {};
  const isHttp = entry.event.startsWith("upstream.");
  const preview = (f.response_preview as string) ?? "";
  const traceback = (f.traceback as string) ?? "";
  const errText = (f.error as string) ?? "";
  const expandable = Boolean(preview || traceback || errText || isHttp);

  return (
    <div className="border-b border-border/40 last:border-0">
      <button
        type="button"
        onClick={() => expandable && setOpen((v) => !v)}
        className={cn(
          "flex w-full items-center gap-3 px-1 py-1.5 text-left text-xs",
          expandable && "hover:bg-muted/40",
        )}
      >
        <span className="shrink-0 tabular-nums text-muted-foreground">{fmtClock(entry.ts)}</span>
        {entry.stage && (
          <Badge variant="outline" className="shrink-0 px-1.5 py-0 text-[10px]">
            {entry.stage}
          </Badge>
        )}
        <span className={cn("shrink-0 font-medium", levelClass[entry.level] ?? "")}>
          {entry.message || entry.event}
        </span>
        {isHttp && (
          <span className="truncate text-muted-foreground tabular-nums">
            {String(f.status ?? "")} · {String(f.url ?? `${f.host ?? ""}${f.path ?? ""}`)} ·{" "}
            {String(f.duration_ms ?? "")}ms · {String(f.response_bytes ?? "")}B
          </span>
        )}
      </button>
      {open && (
        <pre className="mb-2 ml-12 max-w-full overflow-x-auto whitespace-pre-wrap break-all rounded bg-muted/50 p-2 text-[11px] text-muted-foreground">
          {errText && `error: ${errText}\n`}
          {preview && `response: ${preview}\n`}
          {traceback && traceback}
          {!errText && !preview && !traceback && JSON.stringify(f, null, 2)}
        </pre>
      )}
    </div>
  );
}

export function JobLogModal({
  jobId,
  open,
  onOpenChange,
}: {
  jobId: number | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [entries, setEntries] = useState<JobLogEntry[]>([]);
  const [job, setJob] = useState<JobLogResponse["job"] | null>(null);
  const [done, setDone] = useState(false);
  const afterIdRef = useRef(0);

  // (re)open → reset accumulation
  useEffect(() => {
    if (open) {
      afterIdRef.current = 0;
      setEntries([]);
      setDone(false);
      setJob(null);
    }
  }, [open, jobId]);

  const { data } = useQuery({
    queryKey: ["job-logs", jobId],
    queryFn: () => fetchJobLogs(jobId as number, afterIdRef.current),
    enabled: open && jobId != null,
    refetchInterval: (query) => (query.state.data?.done ? false : 2000),
  });

  useEffect(() => {
    if (!data) return;
    setJob(data.job);
    if (data.entries.length) {
      afterIdRef.current = data.latest_id;
      setEntries((prev) => [...prev, ...data.entries]);
    }
    setDone(data.done);
  }, [data]);

  const running = job != null && !done;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-3xl gap-3 overflow-hidden">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-base">
            任务日志
            {job && (
              <Badge
                variant={job.status === "failed" ? "destructive" : job.status === "success" ? "default" : "secondary"}
              >
                {job.status}
              </Badge>
            )}
            {running && (
              <span className="flex items-center gap-1.5 text-xs text-blue-500">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-blue-500" />
                运行中
              </span>
            )}
          </DialogTitle>
        </DialogHeader>

        {job && (
          <div className="text-xs text-muted-foreground tabular-nums">
            发现 {job.items_found} · 保存 {job.items_saved}
          </div>
        )}

        {job?.error_message && (
          <div className="rounded-md bg-red-100 p-3 dark:bg-red-950/50">
            <div className="mb-1 text-xs font-medium text-red-800 dark:text-red-200">错误原因</div>
            <div className="whitespace-pre-wrap break-all text-sm text-red-700 dark:text-red-300">
              {job.error_message}
            </div>
          </div>
        )}

        <div className="min-h-[120px] flex-1 overflow-y-auto rounded-md border border-border/50 bg-card/40 p-2">
          {entries.length === 0 ? (
            <div className="py-8 text-center text-sm text-muted-foreground">暂无日志</div>
          ) : (
            entries.map((e) => <EntryRow key={e.id} entry={e} />)
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd frontend && PATH="/Users/lws/.nvm/versions/node/v18.20.4/bin:$PATH" npx vitest run src/__tests__/job-log-modal.test.tsx`
Expected: PASS（2 passed）。

- [ ] **Step 5: 提交**

```bash
cd frontend && git add src/components/admin/JobLogModal.tsx src/__tests__/job-log-modal.test.tsx
git commit -m "feat(admin-ui): JobLogModal 居中模态任务日志时间线（HTTP/失败行可展开、运行中 live tail）

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: AdminJobsPage 接「日志」按钮 + 移除冗余内联展开

**Files:**
- Modify: `frontend/src/pages/AdminJobsPage.tsx`
- Modify: `frontend/src/__tests__/admin-pages.test.tsx`

**Interfaces:**
- Consumes: `JobLogModal`（Task 7）。

- [ ] **Step 1: 更新测试（补 mock + 断言「日志」按钮）**

在 `frontend/src/__tests__/admin-pages.test.tsx` 的 `vi.mock("../api/client", () => ({ ... }))` 对象里，`fetchJobs` 条目旁补一行：

```typescript
  fetchJobLogs: vi.fn().mockResolvedValue({
    job: { id: 1, status: "success", started_at: null, finished_at: null,
           items_found: 5, items_saved: 5, error_message: "" },
    entries: [], latest_id: 0, done: true,
  }),
```

在 `describe("AdminJobsPage", ...)` 里追加一个断言「日志」按钮存在的用例：

```typescript
  it("renders a 日志 button per job row", async () => {
    render(<AdminJobsPage />, { wrapper: Wrapper });
    expect(await screen.findByText("雪球自选")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "日志" })).toBeInTheDocument();
  });
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd frontend && PATH="/Users/lws/.nvm/versions/node/v18.20.4/bin:$PATH" npx vitest run src/__tests__/admin-pages.test.tsx`
Expected: FAIL — 找不到 name "日志" 的按钮。

- [ ] **Step 3: 改 AdminJobsPage**

import 区：把 `FileText` 加入 lucide 图标导入，并引入 modal；移除不再使用的 `ChevronDown`/`ChevronUp`（内联展开删除后）：

```typescript
import { ChevronLeft, ChevronRight, AlertCircle, CheckCircle2, Clock, RotateCw, Activity, FileText } from "lucide-react";
import { JobLogModal } from "@/components/admin/JobLogModal";
```

组件内：把 `expanded`/`toggle` 状态替换为 modal 状态。删除：

```typescript
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
```
和 `toggle` 函数整段。新增：

```typescript
  const [logJobId, setLogJobId] = useState<number | null>(null);
```

行内：删除 `const isExpanded = expanded.has(j.id);`。在 `<Badge>...</Badge>` 之后，把原来的「失败才显示的 chevron 按钮」整段替换为对所有行显示的「日志」按钮：

```tsx
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 gap-1 px-2 text-xs"
                    onClick={() => setLogJobId(j.id)}
                  >
                    <FileText className="h-3.5 w-3.5" />
                    日志
                  </Button>
```

删除整段失败内联展开块（`{isExpanded && isFailed && ( ... )}`）。

在最外层 `</div>`（`return (<div className="space-y-6">` 对应的收尾）之前，挂载 modal：

```tsx
      <JobLogModal
        jobId={logJobId}
        open={logJobId != null}
        onOpenChange={(o) => { if (!o) setLogJobId(null); }}
      />
```

- [ ] **Step 4: 运行测试 + 类型检查**

Run: `cd frontend && PATH="/Users/lws/.nvm/versions/node/v18.20.4/bin:$PATH" npx vitest run src/__tests__/admin-pages.test.tsx && PATH="/Users/lws/.nvm/versions/node/v18.20.4/bin:$PATH" npx tsc --noEmit`
Expected: 测试 PASS；tsc 无错误（确认删掉的 `ChevronDown/ChevronUp/expanded` 无残留引用）。

- [ ] **Step 5: 提交**

```bash
cd frontend && git add src/pages/AdminJobsPage.tsx src/__tests__/admin-pages.test.tsx
git commit -m "feat(admin-ui): 任务行接入「日志」按钮打开 JobLogModal，移除冗余失败内联展开

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 9: 全量验证 + 文档收尾

**Files:**
- Modify: `CLAUDE.md`（「踩坑记录」补一条，若有）
- 无新代码——纯验证 + 文档。

- [ ] **Step 1: 后端全量测试**

Run: `cd backend && APP_SECRET_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= REDIS_ENABLED=false python3 -m pytest tests/ -q`
Expected: 全绿（含新建 3 个测试文件 + 既有全部）。

- [ ] **Step 2: 前端全量测试**

Run: `cd frontend && PATH="/Users/lws/.nvm/versions/node/v18.20.4/bin:$PATH" npx vitest run`
Expected: 全绿。

- [ ] **Step 3: 前端构建**

Run: `cd frontend && PATH="/Users/lws/.nvm/versions/node/v18.20.4/bin:$PATH" npm run build`
Expected: 构建成功，无类型错误。

- [ ] **Step 4: 在项目 MySQL 环境跑迁移（用户环境）**

Run: `cd backend && alembic upgrade head`
Expected: 升级到 0015，`job_log_entries` 建表成功（注意 `APP_SECRET_KEY` 须在环境中，见近期迁移踩坑）。

- [ ] **Step 5: CLAUDE.md 踩坑补记（如适用）**

在 `## 踩坑记录` 末尾追加：

```markdown
- **任务日志落库 `JobLogHandler`**：挂在 `QueueListener` 的 targets 上，只收带 `crawl_job_id` 的事件；用独立会话批量写、终态事件（`*.completed/*.failed`、WARNING+）强制 flush。新增的业务事件码必须同步注册到 `logging_catalog._EVENT_DESCRIPTIONS`，否则 `test_logging_readability` 失败
```

- [ ] **Step 6: 提交**

```bash
git add CLAUDE.md && git commit -m "docs: 补记任务日志落库踩坑

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage：**
- §1 数据模型 → Task 1 ✓（含 FK CASCADE + 跟随任务保留期，cleanup 走 DB 级联）
- §2 `JobLogHandler` → Task 2（实现）+ Task 3（接入运行时）✓
- §3 落库内容：阶段进度（已有事件，Task 2/3 自动收）✓；HTTP 请求 + 失败响应预览（`observed_http_get` 已含 `response_preview`，自动收）✓；AI 子步骤 → Task 4 ✓；失败 error_type/消息/stage（`crawl.failed` 已含）✓
- §4 API `after_id` 增量 → Task 5 ✓
- §5 「日志查看」按钮 + 居中模态 + live tail → Task 7/8 ✓
- §6 错误处理：DB 不可用静默降级（Task 2 flush try/except）✓；404（Task 5）✓；前端轮询停在 done（Task 7 refetchInterval）✓
- §7 测试 → 每任务 TDD + Task 9 全量 ✓

**Placeholder scan：** 无 TBD/TODO；每个代码步骤含完整代码与确切命令/预期。

**Type consistency：** `fetchJobLogs(jobId, afterId)` / `JobLogResponse{job,entries,latest_id,done}` / `JobLogEntry{id,ts,level,event,category,stage,message,fields}` 在 Task 5（后端返回）、Task 6（类型）、Task 7（消费）三处一致；`after_id` 查询参数后端（Task 5）与 client（Task 6）一致；事件码 `skills.classify.batch`/`skills.translate.batch` 在 Task 4 发与注册一致。

**Decisions locked:** 用全局自增 `id` 作增量游标（无 per-job 内存计数器）；模态复用现有 `Dialog`；范围仅 CrawlJob；移除任务页失败内联展开（被模态取代）。
