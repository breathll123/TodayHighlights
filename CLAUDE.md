# CLAUDE.md

本文件为 Claude Code（claude.ai/code）在此仓库中工作时提供指引。

## 开发命令

```bash
# 后端启动
cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 前端启动
cd frontend && npm run dev -- --host 0.0.0.0 --port 5175

# 运行全部后端测试（SQLite 内存数据库，无需 MySQL）
cd backend && APP_SECRET_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= REDIS_ENABLED=false python3 -m pytest tests/ -v

# 运行单个后端测试文件
cd backend && APP_SECRET_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= REDIS_ENABLED=false python3 -m pytest tests/test_media_cache.py -v

# 运行全部前端测试
cd frontend && npx vitest run

# 运行单个前端测试文件
cd frontend && npx vitest run src/__tests__/market-index-bar.test.tsx

# 生成新的 Alembic 迁移（使用短格式 revision ID）
cd backend && alembic revision --autogenerate -m "描述"

# 初始化或升级数据库（启动应用前执行）
cd backend && python scripts/init_db.py
```

## 架构

### 数据流：适配器 → Block 解析 → API → 前端

```
采集层 (adapters/) → 存储层 (models/) → Block 解析层 (blocks.py) → API → 前端
```

**适配器**（`backend/app/services/adapters/`）是数据源专用的模块。每个适配器函数返回统一的 dict 列表，包含 `id`、`title`、`summary`、`url`、`score`、`source_type` 字段。适配器使用 `@ttl_cache` 进行内存缓存，支持 stale-while-revalidate 策略。

**Block 解析**（`backend/app/services/blocks.py`）通过一个 dispatch 字典将 `PageBlock.source_type` 映射到对应的适配器函数。Block 通过模块级的 `ThreadPoolExecutor` 并行解析。每个 block 的 `source_config` 字典会传给适配器，携带运行时依赖（cookie、media_cache）。

**前端**（`frontend/src/`）使用 React 18 + Vite + TypeScript + Tailwind + shadcn/ui + Framer Motion。页面与主题无关——`TopicPage` 通过 `GridRenderer` 渲染任意主题（股票/足球/AI），`GridRenderer` 将数据类型专用的渲染器（MatchCards、StandingsTable、CompactTable、NewsTimeline 等）包裹在 `CollapsibleSection` 中。

### 模块级注入模式

当某个依赖是线程局部的（每次请求不同），但作为参数传递会导致 `@ttl_cache` 产生不同的缓存 key 时，使用模块级注入：

```python
# 在适配器模块中：
_media_cache = None

def set_media_cache(mc):
    global _media_cache
    _media_cache = mc

# 在 blocks.py 中：调用缓存函数前设置，调用后清除
```

这样既保持了缓存 key 的稳定性，又能传递每次请求的状态。

### 数据库：SQLAlchemy 2.0 + MySQL

- 所有 ORM 模型集中在 `backend/app/models/entities.py`（单文件，不拆分）
- 会话管理通过 `backend/app/core/database.py` — `get_session()` 生成器，供 FastAPI 依赖注入
- MySQL 需要 `pool_pre_ping=True`；连接时设置时区为 `+08:00`
- **测试使用 SQLite 内存数据库** + `StaticPool`——无需 MySQL。conftest 覆盖了 `get_session` 和 `verify_admin` 依赖

### 缓存层

`backend/app/core/cache.py` — `@ttl_cache(ttl_seconds, swr=stale_seconds, maxsize=128)`：
- LRU 淘汰，线程安全
- 缓存 key 格式：`f"{func.__name__}:{args}:{sorted(kwargs.items())}"`
- SWR：在 stale 窗口内返回过期数据，同时通过共享的 `ThreadPoolExecutor` 后台刷新
- 被包装函数暴露 `func.cache_clear()` 方法

### AI 流水线

`ai_enrichment.py` 编排流程：筛选候选条目 → 加载 prompt 模板 → 调用 AI 模型（OpenAI 兼容接口）→ 校验 JSON 输出 → 持久化 highlights + token 用量 + 生成任务。模型 API Key 通过 `CryptoService` 以 Fernet 加密存储。

### 认证

用户密码通过 PBKDF2-SHA256 加盐哈希存储在 `users.password_hash`。新部署先运行 `python scripts/init_db.py`，再由登录页调用 `/api/auth/bootstrap-admin` 创建首个管理员；创建完成后公开注册关闭，仓库和数据库中均不保存默认管理员密码。用户 Token 使用 `app_secret_key` 加密并包含有效期，管理员专属路由使用 `verify_admin` 依赖。

## 设计约束

来自 `PRODUCT.md` 和 `DESIGN.md`：
- **专业终端工具风** — 深色主题（背景 `#0F1419`），高信息密度，避免大面积留白
- **等宽数字** — 所有数据数字使用 `font-feature: 'tnum'` 确保对齐
- **颜色编码**：红涨绿跌（中国股票惯例）；直播状态闪烁
- **AI 是辅助，不是主角** — AI 生成内容必须有明确标识；原始数据始终可见
- **Design tokens** 见 `DESIGN.md`：deep-teal 主色、signal-gold 强调色、terminal-* 表面色、Inter 字体族

### 日志

生产日志系统使用 `QueueHandler` + `QueueListener` + `TimedRotatingFileHandler`：
- `logs/access.log` — HTTP 请求日志（method, path, status, duration_ms, request_id, user_id）
- `logs/application.log` — 业务事件（category=crawler|ai|scheduler）
- `logs/error.log` — 未处理异常（自动关联 request_id）
- 日志脱敏自动处理 API Key、Bearer token、数据库密码、Cookie
- 本地开发命令：`APP_SECRET_KEY=.. REDIS_ENABLED=false python3 -m pytest tests/ -v`（LOG_DIR 自动隔离）

## 踩坑记录

- **FastAPI 路由顺序**：`/token-usages/stats` 必须在 `/token-usages/{usage_id}` 之前注册，否则 stats 路径会被当作 usage_id 捕获
- **Radix UI Select**：`<SelectItem value="" />` 会崩溃——使用哨兵值如 `value="all"`，调用 API 时再映射为 `undefined`
- **MySQL TEXT 列**：不支持 `server_default=""`——TEXT 列省略 `server_default`
- **发布级联删除顺序**：必须先将 `ai_block_analyses` 的 `token_usage_id` 置空 → 删除 `ai_token_usages` → 删除 `ai_generation_jobs` → 删除 `ai_block_analyses` → 删除 `page_blocks`
- **MediaCacheService 会话隔离**：每次操作必须使用独立会话（`_new_session()`），不能共用调用方的会话——否则缓存下载失败会回滚调用方的事务
- **东方财富指数趋势**：日内数据使用 `push2delay.eastmoney.com`（而非 `push2.eastmoney.com`）——主域名可能返回空结果
- **Alembic revision ID**：使用短格式（`"0010"`），不使用长格式（`"20260608_0010"`）
- **`@ttl_cache` key 污染**：不要将每次请求不同的对象（如 `media_cache`）作为参数传给缓存函数——对象的 repr 会成为缓存 key 的一部分，导致缓存几乎无法命中
