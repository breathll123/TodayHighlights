# Redis 实时数据缓存设计

## 目标

将当前 Python 进程内的实时适配器缓存升级为 Redis 共享缓存，解决多设备、多浏览器、多 Uvicorn Worker 场景下重复访问第三方数据源的问题。

首期只处理实时数据缓存，不调整 APScheduler、`crawl_jobs`、`raw_items` 或现有爬虫执行方式。后续升级 Celery、Dramatiq、RQ 或其他调度框架时，任务系统与页面缓存可以独立演进。

## 范围

### 纳入 Redis

- 雪球热股、热门话题、市场热度和筛选器。
- 东方财富实时行业、行情、资金流和公告接口。
- 股票指数快照和分时趋势。
- 球迷屋实时比赛、赛事赛程和积分榜。
- 懂球帝实时比赛适配器。
- AI HOT 资讯。
- DataLearner 模型榜单和指数。

### 不纳入 Redis

- MySQL 中的 `raw_items`、`highlights` 和 `page_blocks`。
- AI 主题总结、区块 AI 分析和 Token 记录。
- 用户、登录状态和后台配置。
- 足球图片文件和 `media_assets` 记录。
- 爬虫任务队列与调度状态。
- 完整页面响应。

## 总体架构

保留现有 `@ttl_cache(...)` 使用方式，将其内部实现替换为 Redis 优先、内存降级的缓存后端：

```text
公开页面请求
    |
    v
实时适配器 @ttl_cache
    |
    +-- Redis 可用
    |     +-- 新鲜数据：直接返回
    |     +-- SWR 数据：返回旧值，仅一个 Worker 后台刷新
    |     +-- 冷启动：仅锁持有者访问第三方，其余请求等待结果
    |
    +-- Redis 不可用
          +-- 自动使用当前进程内 TTL/SWR 缓存
          +-- Redis 恢复后自动切回共享缓存
```

Redis 是正常状态下的唯一缓存判定来源，不作为普通 L1 缓存前再叠加本机内存。这样不同 Worker 不会因为本机缓存时间不同而长时间返回不一致数据。本机内存只在 Redis 故障期间启用。

每次 Redis 写入成功后，同时更新当前进程的内存降级副本。正常请求仍然只读 Redis；只有 Redis 故障或冷启动等待超时时才允许读取该副本。

## 配置

所有连接信息通过环境变量提供：

```env
REDIS_ENABLED=true
REDIS_URL=redis://127.0.0.1:6379/0
REDIS_KEY_PREFIX=today-highlights
REDIS_SOCKET_TIMEOUT_SECONDS=1
REDIS_LOCK_TTL_SECONDS=45
REDIS_RETRY_INTERVAL_SECONDS=30
```

服务器部署时只替换 `REDIS_URL`：

```env
# 带密码
REDIS_URL=redis://:password@redis-host:6379/0

# TLS
REDIS_URL=rediss://:password@redis-host:6380/0
```

要求：

- 代码中不得写死 Redis 主机、端口、密码或数据库编号。
- 日志不得输出完整 `REDIS_URL`，避免泄露密码。
- `REDIS_ENABLED=false` 时直接使用内存缓存，便于测试和紧急降级。
- Redis 连接失败不得阻止 FastAPI 启动。

## 组件设计

### CacheBackend

在 `backend/app/core/cache.py` 中定义内部缓存边界：

```python
class CacheBackend(Protocol):
    def get(self, key: str) -> CacheEnvelope | None: ...
    def set(self, key: str, value: CacheEnvelope, ttl_seconds: int) -> None: ...
    def acquire_lock(self, key: str, token: str, ttl_seconds: int) -> bool: ...
    def release_lock(self, key: str, token: str) -> None: ...
    def clear_function(self, function_id: str) -> None: ...
```

实现：

- `RedisCacheBackend`：共享缓存、分布式锁和跨 Worker 清理。
- `MemoryCacheBackend`：沿用当前线程安全的 LRU、TTL 和 SWR 行为。
- `ResilientCacheBackend`：Redis 优先；成功写 Redis 时镜像内存副本；连接失败后在限定时间内使用内存后端，避免每个请求都重复连接失败。

适配器继续使用 `@ttl_cache`，不直接依赖 Redis 客户端。

### 生命周期

- FastAPI 启动时创建 Redis 连接池并执行一次 `PING`。
- `PING` 失败只记录一次警告，缓存状态设为 `memory-fallback`。
- FastAPI 关闭时关闭 Redis 连接池和 SWR 后台线程池。
- Redis 恢复检测采用按需重试，每隔 `REDIS_RETRY_INTERVAL_SECONDS` 最多尝试一次，不新增常驻健康检查线程。

## 缓存键

函数标识使用完整模块名和函数限定名，避免不同适配器函数重名：

```text
app.services.adapters.xueqiu.fetch_hot_stocks
```

缓存键：

```text
today-highlights:cache:v1:<function-id-hash>:<generation>:<arguments-hash>
```

刷新锁：

```text
today-highlights:lock:v1:<function-id-hash>:<generation>:<arguments-hash>
```

函数版本：

```text
today-highlights:generation:v1:<function-id-hash>
```

参数处理：

- 使用可重复的 JSON 序列化。
- 字典键排序。
- 列表保持顺序。
- 缓存原始函数只允许接收 `None`、布尔值、数字、字符串、列表、元组和字符串键字典等可规范化数据。
- 调用方必须在进入缓存原始函数前移除运行时对象。`MediaCacheService`、SQLAlchemy Session 和 `_media_cache` 只能由公开包装函数使用。
- 缓存框架不得静默跳过任意不可序列化字段。静默跳过会使两个实际不同的调用产生相同 Key，导致错误命中。
- 遇到不支持的参数类型时，记录一次限频 warning，并绕过 Redis 和内存缓存直接执行函数。该行为用于保持服务可用，同时暴露调用边界错误。
- 对序列化结果使用 SHA-256，Redis Key 中不保存 Cookie、URL 参数或其他可能敏感的原始值。

`cache_clear()` 通过递增函数 `generation` 实现跨 Worker 失效，不使用阻塞式 `KEYS`，旧 Key 由 Redis TTL 自动清理。

兼容现有显式别名：

```python
fetch_matches.cache_clear = _fetch_matches_raw.cache_clear
fetch_standings.cache_clear = _fetch_standings_raw.cache_clear
```

Redis 模式下，`cache_clear()` 必须递增共享 generation 并清理当前进程的内存降级副本；内存模式下沿用当前清理行为。当前生产代码没有主动调用这些方法，但测试和后续刷新流程依赖这个公开接口，升级后不得改变语义。

## Value 格式

Redis Value 使用 JSON，不使用 Pickle：

```json
{
  "schema_version": 1,
  "created_at": 1781150400.0,
  "fresh_until": 1781150430.0,
  "value": []
}
```

Redis Key 的实际过期时间为：

```text
ttl_seconds + swr_seconds
```

要求：

- 只缓存 JSON 可序列化的数据。
- 解码失败、版本不支持或结构不合法时按缓存未命中处理，并记录限频警告。
- 不允许反序列化任意 Python 对象。

## 请求和刷新行为

### 新鲜命中

当前时间小于 `fresh_until` 时直接返回 Redis Value，不访问第三方。

### SWR 命中

数据超过新鲜期但尚未超过 Redis TTL 时：

1. 立即返回旧数据。
2. 尝试通过 `SET lock_key token NX EX lock_ttl` 获取刷新锁。
3. 只有锁持有者提交后台刷新任务。
4. 刷新成功后覆盖缓存。
5. 刷新失败时保留旧数据。

### 冷启动或完全过期

1. 第一个请求获取锁并同步访问第三方。
2. 其他请求短暂轮询 Redis，等待第一个请求写入结果。
3. 等待超时后，若本机存在降级副本则返回该副本。
4. 既无 Redis 结果也无降级副本时返回空数据，不允许锁等待者自行访问第三方。

首期冷启动等待上限固定为 2 秒，轮询间隔 50 毫秒。后续如有需要再开放环境变量，不在首期增加配置复杂度。

当前公开 API 是同步 FastAPI 路由，页面请求占用 AnyIO 工作线程，同时实时区块在共享 `ThreadPoolExecutor(max_workers=8)` 中执行。为避免大量冷启动请求把请求线程和区块线程同时占满：

- 每个缓存 Key 在单个进程内最多允许 4 个锁等待者。
- 超过本机等待者阈值的请求不再进入轮询，直接返回内存降级副本；无副本时返回空数据。
- 等待超过 2 秒的请求同样快速降级，不自行访问第三方。
- 持锁请求是该 Key 冷启动期间唯一允许访问第三方的请求。

该策略优先保护线程池和第三方数据源。极端冷启动并发下，少量请求可能暂时看到空区块，但后续前端轮询会自动取得已写入缓存的数据。

### 锁释放

每次加锁生成随机 token。释放锁必须通过 Lua 脚本比较 token 后删除，避免锁过期后误删其他 Worker 新获得的锁。

## 失败语义

新增 `CacheRefreshError`，区分第三方访问失败和合法空数据：

- HTTP 超时、非成功状态、响应解析错误、明显异常的空响应：抛出 `CacheRefreshError`。
- 数据源明确返回“当前无数据”：返回空列表，可正常缓存。
- SWR 刷新抛出 `CacheRefreshError`：保留旧缓存，不写入空列表。
- 冷启动抛出 `CacheRefreshError`：尝试内存降级；仍无数据时由适配器保持现有空列表展示行为。

不能再由已缓存函数把所有异常直接吞掉并返回 `[]`，否则缓存层无法判断是否应该覆盖旧数据。

适配器采用“缓存原始函数 + 公开包装函数”的边界：

```text
_fetch_xxx_raw(...)  -> 抛出 CacheRefreshError，由 @ttl_cache 管理旧数据
fetch_xxx(...)       -> 调用 raw；在缓存和降级都无数据时捕获错误并返回 []
```

这样公开 API 保持现有空数据降级行为，同时缓存层能够正确保留旧值。

## 媒体缓存边界

Redis 只缓存第三方返回的远程数据和远程图片 URL，不缓存请求级对象或本地文件状态。

球迷屋处理方式：

```text
_fetch_matches_raw(...)              -> Redis 缓存
_fetch_competition_schedule_raw(...) -> Redis 缓存
_fetch_standings_raw(...)            -> Redis 缓存

fetch_*()
    -> 读取缓存后的原始结果
    -> 使用 MediaCacheService 补充 *_local 字段
```

`MediaCacheService`、SQLAlchemy Session 和 `_media_cache` 不参与缓存键，也不写入 Redis。这样不会出现缓存中保存已关闭 Session 或旧本地路径的问题。

`_fetch_competition_schedule_raw()` 必须在写入 Redis 前完成远程队徽 URL 解析：

- 赛程 HTML 解析结果包含 `logo_league`、`logo_a` 和 `logo_b`。
- `_get_logo_map()` 和缺失队徽的详情页补充都在持锁刷新流程中完成。
- Redis Value 保存远程队徽 URL，但不保存 `logo_*_local`。
- 公开 `fetch_competition_schedule()` 只负责基于远程 URL 查询或生成本地媒体路径。

现有 `_fill_logo_map()` 最多产生 20 个详情页请求。首期将这些请求限制在唯一锁持有者中，并使用最多 4 个工作线程并发获取，避免每次页面请求产生串行 N+1，同时控制第三方并发量。

## TTL 策略

| 数据 | 新鲜期 | SWR 旧数据期 |
|---|---:|---:|
| 雪球热股、话题、热度、筛选器 | 30 秒 | 300 秒 |
| 东方财富行业和普通行情 | 30 秒 | 300–600 秒 |
| 指数趋势 | 60 秒 | 300 秒 |
| 足球实时比赛 | 30 秒 | 300 秒 |
| 足球赛事赛程 | 300 秒 | 3600 秒 |
| 足球积分榜 | 300 秒 | 3600 秒 |
| 懂球帝比赛 | 30 秒 | 0 秒 |
| AI HOT 资讯 | 300 秒 | 0 秒 |
| DataLearner 榜单与指数 | 600 秒 | 3600 秒 |

首期延续已有 TTL，不改变前端 30 秒或 60 秒轮询频率。

## MySQL 与 Redis 分工

MySQL 继续作为持久化事实来源：

- 数据源配置。
- 定时爬虫抓取结果。
- 原始内容和 AI 结果。
- 页面布局。
- 用户和任务记录。

Redis 只保存可丢失、可重新生成的实时数据缓存和刷新锁。清空 Redis 不应造成持久数据丢失，也不需要数据库迁移。

## 可观测性

启动日志输出以下状态之一：

```text
cache backend: redis
cache backend: memory-fallback
cache backend: memory-disabled
```

现有 `/health` 响应增加非敏感字段：

```json
{
  "status": "ok",
  "cache": "redis"
}
```

日志至少覆盖：

- Redis 初次连接失败和恢复。
- Redis 读写、解码和锁操作失败。
- SWR 后台刷新失败。
- 冷启动等待超时。

相同 Redis 错误需要限频，避免服务故障时刷满日志。日志不得包含 Cookie、API Key、完整 Redis URL 或缓存 Value。

首期不引入命中率指标系统；为后续 Prometheus 指标保留内部事件计数接口即可。

## 未来调度框架边界

Redis 缓存模块不得导入 APScheduler、`run_crawl_job` 或任务模型。

未来调度系统可以：

- 使用相同 Redis 实例的不同数据库编号或不同 Key Prefix。
- 将定时抓取任务交给 Celery、Dramatiq、RQ 或其他 Worker。
- 抓取成功后通过 `cache_clear()` 或 generation 递增使相关实时缓存失效。

首期不预埋任务队列抽象，也不把公开页面的实时适配器改成队列任务。

## 改动文件

- `backend/app/services/ai_block_analysis.py`
  - 在 Redis 改造前单独修复 `generatsed_by_model` 和 `tatus` 拼写错误。
- `backend/tests/test_ai_block_analysis.py`
  - 验证成功分析会写入 `status="generated"` 和 `generated_by_model`。
- `backend/pyproject.toml`
  - 增加同步 Redis 客户端依赖。
- `backend/.env.example`
  - 增加 Redis 环境变量示例。
- `backend/app/core/config.py`
  - 增加 Redis 配置字段。
- `backend/app/core/cache.py`
  - 实现 Redis、内存和故障切换后端。
  - 保持 `ttl_cache` 的现有调用方式。
- `backend/app/main.py`
  - 初始化、检查并关闭缓存连接。
  - `/health` 返回缓存后端状态。
- `backend/app/services/adapters/*.py`
  - 统一刷新失败语义。
  - 将球迷屋赛程拆分为原始缓存和媒体补充两层。
- `backend/tests/test_cache.py`
  - 覆盖 Redis 命中、过期、SWR、锁和内存降级。
- `backend/tests/test_qiumiwu_media_cache.py`
  - 验证 Redis 缓存结果不包含请求级媒体缓存对象和过期本地路径。
- `backend/tests/conftest.py`
  - 在导入 FastAPI 应用前默认设置 `REDIS_ENABLED=false`，避免普通测试依赖开发机 Redis。
- `README.md`
  - 补充本机和服务器 Redis 配置与故障降级说明。
- `CLAUDE.md`
  - 测试命令显式增加 `REDIS_ENABLED=false`。

不需要 Alembic 迁移，也不修改前端 API。

## 测试策略

### 单元测试

- 相同参数生成相同 Key，不同参数生成不同 Key。
- 敏感参数不以明文出现在 Key 中。
- 不支持的参数类型不会被静默丢弃，也不会写入缓存。
- 新鲜 Redis 命中不执行被装饰函数。
- SWR 命中立即返回旧值。
- 并发 SWR 请求只有一个获得刷新锁。
- 刷新失败不覆盖旧值。
- 冷启动并发请求优先等待锁持有者结果。
- 单 Key 等待者超过阈值后快速返回降级值，不继续占用轮询线程。
- 锁等待超时不会触发额外第三方请求。
- 锁只能由相同 token 释放。
- `cache_clear()` 在多个后端实例间生效。
- 现有 `fetch_matches.cache_clear()` 和 `fetch_standings.cache_clear()` 别名继续有效。
- Redis 连接失败时自动使用内存缓存。
- Redis 恢复后重新使用 Redis。
- 非 JSON 结果不写入 Redis，并安全退回内存。

普通后端测试在 `backend/tests/conftest.py` 中于应用导入前默认设置 `REDIS_ENABLED=false`，并在 README 和 CLAUDE 开发命令中显式保留：

```bash
APP_SECRET_KEY=... REDIS_ENABLED=false python3 -m pytest tests/ -v
```

Redis 专项测试使用 Fake Redis 或注入式 Redis 客户端，并在测试内显式启用对应后端，不依赖开发机正在运行的 Redis。

### 集成验证

- 启动本机 Redis 后，连续请求股票页，确认第三方适配器在 TTL 内只执行一次。
- 使用两个后端进程请求同一页面，确认共享同一缓存。
- 停止 Redis，确认页面继续返回数据且 `/health` 显示 `memory-fallback`。
- 恢复 Redis，确认无需重启后端即可回到 `redis`。
- 验证足球赛程、比赛和积分榜的本地队徽路径仍然有效。
- 运行完整后端测试和前端回归测试。

## 验收标准

- 新设备或新浏览器访问不会在 TTL 内重复触发同一实时第三方请求。
- 多个 Uvicorn Worker 共享缓存和刷新锁。
- Redis 故障不会阻止服务启动，也不会让公开页面整体报错。
- Redis 恢复后自动重新接管缓存。
- 有效旧数据不会被第三方故障产生的空列表覆盖。
- 数据库区块、AI 结果、媒体文件和现有爬虫调度行为不变。
- 所有 Redis 连接配置均来自环境变量。
