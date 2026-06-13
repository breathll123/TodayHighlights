# 生产级文件日志系统设计

## 背景

今日看点部署到服务器后，当前只能看到 Uvicorn 的基础启动和访问输出。部分模块已经调用 Python `logging`，但没有统一配置；更多数据适配器使用 `except Exception` 返回空列表或忽略失败，导致第三方接口、解析、入库、AI 调用和定时任务问题难以定位。

本次建立生产级文件日志系统，目标是让服务器运维人员只通过日志文件就能回答：

- 哪个 HTTP 请求失败，耗时多少，由谁触发。
- 哪个数据源在请求、解析、去重或入库阶段失败。
- 哪个 AI 任务调用了什么模型，耗时和 Token 用量是多少。
- 哪个定时任务何时触发、跳过或失败。
- MySQL、Redis、文件系统或后台线程是否出现系统级异常。

首版不做后台日志查看页面，不引入 ELK、Loki、Sentry 或数据库日志表。

## 设计原则

- 日志按用途分流，不把同一条业务日志重复写入多个文件。
- 使用结构化文本，兼顾人工阅读、`grep` 和后续日志采集。
- 业务失败与系统异常分开，避免 `error.log` 被可预期的第三方错误淹没。
- 请求、采集任务和 AI 任务通过上下文 ID 关联。
- 默认不记录请求体、模型输入输出和敏感配置。
- 日志故障不能阻止主应用启动或影响正常请求。
- 日志策略通过环境变量配置，业务模块不关心按天还是按小时滚动。

## 文件分类

日志目录默认位于 `backend/logs/`：

```text
logs/
├── access.log
├── application.log
└── error.log
```

### `access.log`

只记录 HTTP 请求结果：

- 时间、日志级别、事件名。
- `request_id`。
- HTTP 方法和路径。
- 查询参数名称，不记录参数值。
- 状态码、耗时、客户端 IP。
- 已认证用户 ID；匿名请求记为 `-`。
- 是否为慢请求。

示例：

```text
2026-06-13 14:20:31.218 INFO event=http_request_completed request_id=01JX... method=GET path=/api/public/market-indices query_keys=- status=200 duration_ms=842 client_ip=203.0.113.10 user_id=- slow=false
```

### `application.log`

记录已被业务边界处理的运行过程，通过 `category` 区分：

- `crawler`：采集任务、外部请求、解析、去重和入库。
- `ai`：模型调用、重试、Token、输出校验和生成任务。
- `scheduler`：定时任务触发、完成、跳过和失败。
- `cache`：Redis 启动、降级、恢复、锁和后台刷新。
- `media`：媒体下载、缓存命中和文件处理。
- `database`：迁移、批量写入和业务事务回滚。
- `system`：应用启动、关闭和非异常运行状态。

示例：

```text
2026-06-13 14:20:31.218 INFO category=crawler event=crawl_job_finished request_id=- crawl_job_id=128 source_id=3 source=eastmoney trigger=scheduled duration_ms=842 items_found=6 items_saved=6
```

第三方 `403`、超时、解析失败、AI JSON 校验失败等可预期且已被业务逻辑处理的失败写入此文件，并带 `result=failed`、`stage` 和非敏感错误摘要。

### `error.log`

只记录影响系统边界的错误：

- FastAPI 未捕获异常和完整堆栈。
- MySQL、Redis、文件系统等基础设施故障。
- 调度器线程未捕获异常。
- 后台刷新线程和线程池逃逸异常。
- 日志系统初始化或写入故障。
- 应用启动、关闭阶段失败。

示例：

```text
2026-06-13 14:20:31.218 ERROR event=unhandled_http_exception request_id=01JX... method=GET path=/api/public/pages/topics/stocks/blocks exception_type=OperationalError message="database connection lost"
Traceback ...
```

HTTP 500 会在 `access.log` 留请求结果摘要，在 `error.log` 留异常堆栈。两条记录通过相同 `request_id` 关联，这是唯一允许的跨文件关联记录。

## 日志格式

采用单行结构化文本：

```text
<time> <level> category=<category> event=<event> key=value ...
```

约束：

- 时间使用 `Asia/Shanghai`，精确到毫秒。
- 字段名使用小写下划线。
- 事件名使用稳定的英文标识，不把自然语言作为事件名。
- 字符串包含空格、换行或特殊字符时进行安全转义和引号包裹。
- 单条日志最大长度由 `LOG_MAX_MESSAGE_LENGTH` 控制。
- 超长内容截断后追加 `truncated=true`。
- 堆栈允许多行，仅存在于 `error.log`。

每条记录必须显式带有内部 `log_channel`，值为 `access`、`application` 或 `error`。分流过滤器按此字段选择唯一文件；该内部字段不输出到最终文本。

没有显式通道的第三方库日志按以下规则处理：

- `ERROR` 及以上进入 `error.log`。
- `WARNING` 及以下进入 `application.log`。
- Uvicorn 默认访问日志关闭，由自定义 HTTP 中间件统一生成 `access.log`，避免重复。

## 上下文关联

使用 `ContextVar` 保存日志上下文，不修改每个函数签名：

- `request_id`
- `crawl_job_id`
- `ai_job_id`
- `source_id`
- `user_id`

HTTP 请求进入时：

1. 接受格式合法的 `X-Request-ID`，否则生成新的不可预测 ID。
2. 将 ID 写入上下文。
3. 响应头返回 `X-Request-ID`。
4. 请求结束后清理上下文，避免线程复用造成污染。

手动触发采集或 AI 时继承当前 `request_id`。定时任务没有 HTTP 请求，`request_id` 为 `-`，但必须携带任务 ID。

线程池和后台线程不会自动可靠继承所有上下文。提交任务时使用显式上下文复制，或在任务入口重新绑定任务 ID；任务退出时必须清理。

## HTTP 日志

新增 FastAPI 中间件，记录：

- `http_request_started` 仅在 `DEBUG` 级别启用。
- `http_request_completed` 记录所有完成请求。
- `http_request_client_error` 记录 4xx。
- `http_request_server_error` 记录已转换为响应的 5xx。
- 未捕获异常交给统一异常边界写入 `error.log`，再返回正常的 500 响应。

不记录：

- 请求体和响应体。
- `Authorization`、`Cookie`、`Set-Cookie`。
- 上传文件内容。
- 查询参数值。

健康检查 `/health` 默认记录，但可通过 `LOG_ACCESS_EXCLUDE_PATHS` 排除，防止监控探针刷日志。

客户端 IP 优先读取可信反向代理传入的 `X-Forwarded-For`。只有部署明确设置可信代理后才使用该头，否则使用连接地址，避免伪造。

## 数据采集日志

`run_crawl_job` 是采集任务的主边界，至少记录：

1. `crawl_job_started`
   - `crawl_job_id`
   - `source_id`
   - `source`
   - `trigger`
   - `entry_type`
2. `crawl_fetch_finished`
   - `provider`
   - `operation`
   - `duration_ms`
   - `http_status`
   - `attempt`
3. `crawl_parse_finished`
   - `items_received`
   - `items_valid`
   - `items_skipped`
4. `crawl_persist_finished`
   - `items_found`
   - `items_saved`
   - `items_deduplicated`
5. `crawl_job_finished`
   - `result`
   - 总耗时和数量
6. `crawl_job_failed`
   - `stage=fetch|parse|persist|enrichment`
   - `exception_type`
   - 脱敏后的错误摘要

各适配器不再静默吞掉异常。允许返回空数据的业务情况需要记录明确事件，例如 `crawl_empty_result`；真正的异常应向任务边界传播，或在适配器内记录后返回有类型的失败结果。

外部请求日志不得记录完整 URL 查询字符串。只记录：

- `provider`
- `host`
- `path`
- HTTP 方法
- 状态码
- 耗时
- 重试次数

Cookie、签名、API Key 和查询参数值全部省略。

## AI 日志

AI 日志覆盖单条加工、主题摘要、方块分析和 Artificial Analysis 同步。

模型调用开始：

```text
category=ai event=ai_request_started ai_job_id=... usage_type=block_analysis provider=openai_compatible model=... attempt=1
```

完成时记录：

- `ai_job_id`
- `usage_type`
- 模型名和模型配置 ID
- `duration_ms`
- `prompt_tokens`
- `completion_tokens`
- `total_tokens`
- Token 是否为估算值
- 输出校验结果
- 重试次数

失败时记录：

- `stage=request|transport|decode|validation|persist`
- HTTP 状态码（如有）
- 异常类型
- 脱敏错误摘要
- 是否可重试
- 当前尝试次数

默认禁止记录：

- System Prompt 和 User Prompt 原文。
- 模型完整输出。
- API Key 和 Authorization。
- 输入文章正文。

为了排查模型格式问题，可以记录非内容型信息，例如输出字符数、JSON 字段名、缺失字段名和校验错误。未来如确需记录 Prompt，必须通过单独的显式开关启用，并进行长度限制和敏感信息过滤；首版不提供该开关。

Artificial Analysis 的日志额外记录：

- 数据集 key。
- 分页页码。
- 响应字节数。
- 配额剩余值。
- 快照 ID、数据集 ID和入库条数。

不得记录 `x-api-key`。

## 调度器日志

调度器至少记录：

- `scheduler_started` 和已注册任务 ID。
- `scheduled_job_started`。
- `scheduled_job_finished`，包含耗时和结果。
- `scheduled_job_skipped`，包含并发锁、缺少配置等原因。
- `scheduled_job_failed`。
- `scheduler_stopped`。

通过 APScheduler listener 捕获执行成功、失败和错过执行时间事件，避免只依赖任务函数内部日志。

采集调度器触发 `run_crawl_job` 后，调度日志只描述调度动作；采集细节写 `category=crawler`，避免同一过程重复记录。

## 缓存、媒体和数据库日志

### Redis

记录启动状态、降级、恢复、SWR 刷新失败和锁等待超时。相同错误按错误指纹限频，恢复时必须重新记录一次状态。

日志不得包含完整 Redis URL、缓存 Value 或锁 Token。

### 媒体缓存

记录 provider、资源类型、URL 哈希、缓存命中、下载耗时、文件大小和失败阶段。不得记录包含签名参数的完整远程 URL。

### 数据库

不启用 SQLAlchemy 全量 SQL 日志，避免日志量和敏感数据泄露。只记录：

- 数据库连接或事务失败。
- 关键批量写入数量和耗时。
- 迁移开始、完成和失败。
- 事务回滚原因摘要。

## 脱敏

所有日志在格式化前经过统一脱敏器。字段名不区分大小写，命中以下模式时值替换为 `[REDACTED]`：

- `api_key`
- `x-api-key`
- `authorization`
- `cookie`
- `set-cookie`
- `password`
- `secret`
- `token`
- `access_token`
- `refresh_token`

错误字符串还需处理：

- URL 中的用户名、密码和敏感查询参数。
- `redis://user:password@host`。
- `mysql+pymysql://user:password@host`。
- Bearer Token。
- 常见 API Key 请求头文本。

脱敏发生在队列入队前，避免敏感数据短暂保留在日志队列对象中。

## 轮转与保留

默认按天零点滚动：

```text
access.log.2026-06-12
application.log.2026-06-12
error.log.2026-06-12
```

配置：

```env
LOG_DIR=logs
LOG_LEVEL=INFO
LOG_ROTATION=daily
LOG_RETENTION_DAYS=14
LOG_MAX_MESSAGE_LENGTH=4000
LOG_CONSOLE_ENABLED=true
LOG_SLOW_REQUEST_MS=2000
LOG_ACCESS_EXCLUDE_PATHS=
LOG_TRUST_PROXY_HEADERS=false
```

规则：

- `LOG_ROTATION=daily` 使用每天零点轮转。
- 内部同时支持 `hourly`，后续只改 `.env` 即可切换。
- `LOG_RETENTION_DAYS` 同时作用于三个文件。
- 当前活动日志永远不删除。
- 启动时执行一次兜底清理；轮转时再由 handler 清理历史文件。
- 非法配置回退到安全默认值并记录警告。

首版保持单进程：

```text
uvicorn app.main:app --workers 1 --no-access-log
```

原因是标准 `TimedRotatingFileHandler` 不保证多个进程同时轮转安全，而且当前 APScheduler 也要求单 Worker。未来拆分调度器并扩展多 Worker 时，再更换支持多进程的日志 handler 或集中式日志采集。

## 异步写入与生命周期

使用标准库：

- `QueueHandler`
- `QueueListener`
- `TimedRotatingFileHandler`

需要实现轻量自定义 `QueueHandler.prepare()`：

- 在入队前复制 `LogRecord`，不修改调用方持有的原记录。
- 先完成字段脱敏和长度限制。
- 保留结构化字段、`exc_info` 和堆栈文本，确保监听线程能写出完整异常。
- 移除不可序列化且与日志无关的临时对象。

启动顺序：

1. 解析日志配置。
2. 创建日志目录和 handlers。
3. 启动 `QueueListener`。
4. 初始化 FastAPI、Redis 和调度器。

退出顺序：

1. 停止调度器和后台线程。
2. 写入 `application_stopping`。
3. 刷新并停止 `QueueListener`。
4. 关闭文件 handler。

如果日志目录创建失败：

- 启用同步控制台 fallback。
- 输出一次明确警告。
- 应用继续启动。
- 不尝试在每条日志上重复创建目录。

日志队列设置有界容量。队列满时不得阻塞业务线程，丢弃低优先级日志并通过限频的控制台警告报告；`ERROR` 记录优先同步写入 fallback。

`ERROR` 的同步 fallback 只在入队失败后执行，不能同时进入队列和 fallback，避免同一异常重复写入。

## 模块边界

新增核心模块：

```text
app/core/logging.py
```

职责：

- 解析日志配置。
- 初始化和关闭队列日志系统。
- 格式化、分流和脱敏。
- 管理上下文变量。
- 提供结构化事件辅助函数。
- 提供限频机制。

业务模块只调用稳定接口，例如：

```python
log_event(
    logger,
    channel="application",
    category="crawler",
    event="crawl_job_finished",
    crawl_job_id=job.id,
    items_found=len(drafts),
)
```

业务代码不得直接创建文件 handler，不得自行拼接敏感字段，不得依赖具体日志文件名。

## 错误处理规则

错误分为三类：

1. **业务可预期失败**
   - 第三方 4xx/5xx、超时、空结果、模型校验失败。
   - 写 `application.log`。
   - 任务状态按现有数据库模型更新。
2. **业务边界内未知失败**
   - 任务入口捕获未知异常，任务可正常标记失败。
   - 写 `application.log`，附有限堆栈或异常摘要。
   - 如果同时表明基础设施不可用，则升级到 `error.log`。
3. **逃逸异常**
   - FastAPI、调度线程或后台线程未捕获异常。
   - 写 `error.log` 完整堆栈。

不能继续使用无日志的空 `except Exception`。确实需要忽略的清理失败也必须使用限频的 `DEBUG` 或 `WARNING` 事件说明原因。

## 测试策略

### 核心日志测试

- 三类事件只进入目标文件。
- 未分类第三方日志按级别正确回退。
- 结构化文本正确转义。
- 超长消息截断。
- 敏感字段和错误字符串脱敏。
- 按天和按小时轮转配置映射正确。
- 保留天数和启动清理正确。
- 日志目录不可写时降级到控制台。
- 队列满时不阻塞调用线程。

### HTTP 测试

- 响应包含 `X-Request-ID`。
- 合法传入 ID 被沿用，非法 ID 被替换。
- access 日志包含状态码和耗时。
- 查询参数只记录名称。
- Authorization 和 Cookie 不出现在日志。
- HTTP 500 的 access 摘要和 error 堆栈共享 `request_id`。

### 业务测试

- 采集成功记录 fetch、parse、persist 和 finished 事件。
- 采集失败记录准确 `stage`。
- AI 成功记录 Token 和耗时，不记录 Prompt。
- AI 校验失败记录字段错误，不记录模型原文。
- APScheduler listener 记录成功、失败和 missed。
- Redis、媒体缓存和 Artificial Analysis 的敏感配置不泄露。

### 验收

在服务器运行一次：

- 正常页面请求。
- 一个成功采集任务。
- 一个故意配置错误的数据源。
- 一次 AI 生成。
- 一次定时任务。

确认可以仅通过三个日志文件追踪完整过程，并通过 ID 关联对应数据库任务。

## 部署与运维

宝塔部署时创建目录：

```bash
cd /root/projects/daily_highlights/TodayHighlights/backend
mkdir -p logs
chmod 750 logs
```

目录所有者必须与宝塔 Python 项目的启动用户一致。

启动命令增加：

```text
--workers 1 --no-access-log
```

常用排查命令：

```bash
tail -f logs/access.log
tail -f logs/application.log
tail -f logs/error.log
grep 'crawl_job_id=128' logs/application.log
grep 'request_id=01JX' logs/access.log logs/error.log
grep 'category=ai' logs/application.log
```

日志目录不纳入 Git，部署和备份策略需明确排除或单独归档。

## 非目标

- 不增加后台日志查看页面。
- 不把运行日志写入 MySQL。
- 不记录完整请求体、响应体、Prompt 或模型输出。
- 不接入远程日志服务。
- 不支持多 Worker 共同写同一组轮转文件。
- 不改变现有任务数据库日志和状态模型；文件日志作为运行排障补充，不替代任务事实记录。
