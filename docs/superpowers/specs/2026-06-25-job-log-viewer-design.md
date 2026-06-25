# 任务日志查看器 + 按任务日志落库 — 设计

- 日期：2026-06-25
- 状态：已与用户确认设计，待写实施计划
- 范围：后台【任务】页（CrawlJob）每行新增「日志查看」入口，弹出该任务的完整日志时间线；为此给日志系统接一个「按 job 聚合」的可查询落点。

## 背景与问题

后台【任务】页展示 `CrawlJob` 行（`GET /admin/jobs`）。每条任务在 DB 里只存了：`status`、起止时间、`items_found/saved`、`error_message`、`log_excerpt`（失败时异常字符串前 500 字，成功时为空）。

底层日志系统其实**已经**记录了丰富的事件——`crawl.started` → `crawl.fetch.completed` → `crawl.persist.completed` → `crawl.completed/failed`，以及每个 HTTP 请求（`observed_http_get`，含脱敏 URL/状态码/耗时）。每条日志行都带 `crawl_job_id`。但这些只写进 `logs/application.log`/`error.log`（每天 5–50MB、按天滚动的文本文件），**后台 UI 读不到**。

后果（用户痛点）：
1. 运行中的任务不知道卡在哪里（只有 `status="running"`，无可见进度）。
2. 失败原因不清楚（只有 500 字异常串，无 traceback、无失败阶段、无具体请求/响应）。
3. 对日志「看不到具体请求、看不到错误内容」不满。

数据其实存在，缺的是**按任务的出口**。

## 目标

- 【任务】页每行一个「日志查看」按钮 → 居中弹出模态，展示该任务**结构化、可读**的日志时间线。
- 运行中任务可**实时（轮询增量）**看进度，知道卡在哪。
- 失败任务能看到**错误类型、消息、失败阶段、traceback、相关请求与响应预览**。
- 不为省时降质：清晰边界、可测试、配套测试齐全（遵守 CLAUDE.md 质量约束）。

## 非目标（YAGNI）

- 只接 **CrawlJob**（skills 同步、AI enrichment 都已折进 CrawlJob，自动覆盖）；**不**动 `AIGenerationJob` 那条独立线。
- **不**重写日志文件的格式/滚动策略——文件本身已是结构化的；本设计提供的是「按任务」出口，不是重写文件日志。
- 表结构用 `crawl_job_id` 直接外键，**不**提前做泛化 `job_kind` 字段；真要给 AI 线加时再扩。

## 关键实现选择：日志条目怎么写进表

事件已在发，每条带 `crawl_job_id`。问题只是「在哪接一个落库的水龙头」。

- **方案 A（采纳）— 日志管线挂一个 `JobLogHandler`：** 给现有 `QueueListener` 的 targets 加一个 handler，筛出带 `crawl_job_id` 的记录就落库。零改任务代码；自动覆盖阶段事件 + `observed_http_get` 请求 + AI 子步骤（只要在 `crawl_job_id` 上下文内）；写在后台 listener 线程、用独立 session，不阻塞任务、不污染任务事务；脱敏复用现有 `sanitize_fields`（记录进管线前已脱敏）。
- 方案 B（否决）— 任务代码显式调 recorder：每个阶段/请求手动再记一遍，易漏（尤其 adapter 内 HTTP）、双重记账、需自管事务与脱敏。

采纳 A。它把「已经在记的东西」多接一个出口，几乎不碰业务代码，且符合项目「MediaCacheService 会话隔离」铁律。

## 设计

### 1. 数据模型 — 新增 `job_log_entries`

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | BIGINT PK | 全局自增；**直接用作增量轮询游标**（`after_id`），无需另设 per-job 序号，避免内存计数器跨重启冲突 |
| `crawl_job_id` | FK → `crawl_jobs.id` ON DELETE CASCADE | 跟随任务保留期，级联自动清理 |
| `ts` | DATETIME | 事件时间 |
| `level` | VARCHAR | INFO / WARNING / ERROR |
| `channel` | VARCHAR | application / access |
| `event` | VARCHAR | `crawl.fetch.completed` / `http.get` / `skills.classify.batch` … |
| `category` | VARCHAR | crawler / ai |
| `stage` | VARCHAR | fetch / persist / enrichment / skills_sync …（来自上下文） |
| `message` | TEXT | 人读的一行 |
| `fields_json` | JSON | 脱敏后的结构化明细：URL、状态码、耗时、found/saved、error_type、traceback、response_preview… |

索引：`(crawl_job_id, id)`。

保留期：`crawl_jobs` 现有 `cleanup_old_crawl_jobs` 删旧任务时，外键级联自动带走日志——零额外保留逻辑。Alembic 迁移用短格式 revision id（接在当前 head 之后）。

### 2. 采集侧 — `JobLogHandler`（日志系统唯一改动点）

`app/core/logging.py` 新增 handler，挂到现有 `QueueListener` 的 targets：

```python
class JobLogHandler(logging.Handler):
    def emit(self, record):
        fields = getattr(record, "event_fields", {})
        job_id = fields.get("crawl_job_id")
        if job_id is None:
            return                       # 只收带 job 上下文的事件
        # 缓冲，批量 flush；用独立 session 写入，失败静默吞掉
```

要点：
- 在 **listener 线程**运行，不阻塞任务；用**独立 session**，写失败绝不回滚任务事务。
- **批量 flush**（攒 ~50 条或 ~250ms），降低高频 HTTP 源写压力。
- 顺序由全局自增 `id` 天然保证单调，handler 不维护任何 per-job 内存计数器。
- `fields_json` 取 `record.event_fields`——已过 `sanitize_fields` 脱敏（URL/Key/Cookie 已处理）；`response_preview` 复用现有 `log_response_preview_chars` 设置（默认 500 字）。
- 在 `LoggingRuntime.start()` 把该 handler 加入 `targets`，随 listener 一起启停；DB 不可用时 handler 静默降级，不影响文件日志。

### 3. 落库哪些事件

| 来源 | 现状 | 改动 |
|---|---|---|
| 阶段进度 | `crawl.started/fetch.completed/persist.completed/completed/failed` 已发 | 无需改，handler 自动收。失败事件已带 `error_type`+消息+`stage`，**补存 `traceback` 进 `fields_json`**（明细备查，不刷屏） |
| 每个 HTTP 请求 | `observed_http_get` 已发请求事件、带上下文 | 确认所有 adapter 走它（已是）；失败时**补 `response_preview`**（前 N 字、脱敏、截断） |
| AI 子步骤 | skills 仅失败时记 | **补几条 `log_event`**：classify/translate 每批的 started/done（模型、批次、Token、耗时——不记 Prompt，守 AI 日志规约） |

### 4. API

```
GET /admin/jobs/{job_id}/logs?after_id=<n>
  → {
      job: { id, status, started_at, finished_at, items_found, items_saved, error_message },
      entries: [ { id, ts, level, event, category, stage, message, fields } ],
      latest_id: <int>,
      done: <bool>   # status in (success, failed)
    }
```

- `after_id` 支持**增量轮询**：运行中前端只拉 `id > after_id` 的新条目。
- `done` 供前端停止轮询。
- 复用 `verify_admin` 依赖；条目按 `id` 升序。
- 路由顺序注意：`/jobs/{job_id}/logs` 与现有 `/jobs` 列表不冲突；遵守项目「具体路径先于通配」习惯。

### 5. 前端 — 「日志查看」按钮 + 居中模态时间线

- **`AdminJobsPage`** 每行操作区加一个 `FileText` 图标按钮「日志」。
- 点击 → **居中弹出 `JobLogModal`**，复用项目现有 `src/components/ui/dialog.tsx`（与 BlockEditor / Sources 等同一套模态 + 动效），终端深色、大尺寸、body 可滚动：
  - **顶部**：任务概况条（状态徽章、源、触发方式、起止、found/saved）。
  - **失败时**：醒目红色错误块（error_type + 消息 + 失败阶段；traceback 可展开）。
  - **时间线 body**：每条一行——时间 / 阶段徽章 / 事件 / 关键字段。HTTP 行展示 `GET 状态码 · 脱敏URL · 耗时 · 字节`，失败请求可展开看响应预览；AI 行展示模型/批次/Token/耗时。
  - **运行中**：顶部「运行中」脉冲指示 + 每 ~2s 用 `after_id` 增量轮询追加新行（live tail），任务 `done` 后自动停。
  - 行号为客户端按列表位置派生的 1-based 展示序号（不依赖后端）。
- 等宽数字（`tnum`）、颜色编码沿用 DESIGN.md。
- API client 新增 `fetchJobLogs(jobId, afterId?)` + 类型。

### 6. 错误处理

- DB 不可用时 `JobLogHandler` 静默降级，文件日志不受影响。
- handler 写入失败用独立 session 回滚自身，绝不影响任务事务。
- API：job 不存在 → 404；`after_id` 越界 → 返回空 `entries` + 当前 `latest_id`。
- 前端：模态加载失败显示错误态而非崩溃；运行中轮询出错退避后重试。

### 7. 测试

- **后端**：`JobLogHandler` 筛选+落库（带/不带 `crawl_job_id`）；`id` 单调有序；脱敏字段已生效；`GET /jobs/{id}/logs` 全量 + `after_id` 增量；级联删除（删 job 带走日志）。
- **前端**：modal 渲染时间线、失败块、HTTP 行展开；运行中轮询 mock 出新条目；`vitest` 全绿。
- 全部走现有 SQLite 内存（后端）+ node18（前端）跑通后才算完成。

## 涉及文件（预估）

- 后端：`app/models/entities.py`（`JobLogEntry`）、新 Alembic 迁移、`app/core/logging.py`（`JobLogHandler` + 接入 `LoggingRuntime`）、`app/services/skills/classify.py`（AI 子步骤事件）、`app/api/admin.py`（`/jobs/{id}/logs`）、`tests/`。
- 前端：`src/pages/AdminJobsPage.tsx`、`src/components/admin/JobLogModal.tsx`（新）、`src/api/client.ts`（`fetchJobLogs` + 类型）、`src/__tests__/`。
