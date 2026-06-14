# 今日看点

一个面向股票、足球和 AI 等主题的多源信息聚合与智能看板系统。

项目提供可配置的数据接入、定时任务、内容存储、AI 辅助处理和可视化展示能力。管理员可以通过后台组合不同的数据方块，建立适合不同主题的信息工作台。

## 主要功能

- **多主题看板**：内置股票、足球、AI 主题页面，并支持继续扩展新主题
- **可视化布局**：拖拽配置方块位置、尺寸、展示样式、字段和排序规则
- **数据连接器**：通过统一 Adapter 接口接入授权 API、RSS、本地数据或其他合规数据源
- **任务调度**：按数据源配置周期执行同步任务，并记录运行状态和错误信息
- **内容管理**：保存原始条目、摘要内容、热度指标和发布状态
- **AI 辅助处理**：支持内容增强、主题摘要、方块分析和提示词模板
- **AI 运维统计**：记录生成任务、模型调用和 Token 使用情况
- **后台管理**：提供数据源、主题、用户、模型、任务和页面布局管理
- **安全初始化**：首次访问时创建管理员，不提供公开的默认账号或密码

## 技术栈

| 模块 | 技术 |
|------|------|
| 后端 | FastAPI、SQLAlchemy 2.0、MySQL、Alembic、APScheduler |
| 前端 | React 18、Vite、TypeScript、Tailwind CSS、shadcn/ui |
| 数据接入 | Adapter 模式、HTTP 客户端、定时任务 |
| AI | OpenAI 兼容接口、可配置模型和提示词 |
| 测试 | Pytest、Vitest、Testing Library |

## 系统架构

```text
数据连接器                数据处理与存储                 页面展示
Adapter / Source   ->   RawItem / Highlight   ->   PageBlock / Dashboard
授权 API / RSS          AI 增强与主题摘要              卡片 / 列表 / 时间线
本地数据                 任务与用量记录                 股票 / 足球 / AI
```

数据连接器负责将不同来源转换为统一结构。数据进入存储层后，可以经过 AI 辅助处理，再由可配置的页面方块完成展示。连接器、内容处理和页面布局相互独立，便于增加新的主题和数据类型。

## 项目结构

```text
backend/
  app/api/                 HTTP API
  app/models/              数据模型
  app/services/adapters/   页面实时数据连接器
  app/sources/             后台同步数据连接器
  app/services/            内容、AI、任务和缓存服务
  migrations/              数据库迁移
  scripts/init_db.py       数据库初始化脚本

frontend/
  src/pages/               公共页面与管理页面
  src/components/          看板、表格、卡片和表单组件
  src/api/                 API 客户端与类型
```

## 快速开始

### 1. 启动后端

```bash
cd backend
conda activate daily_highlights
cp .env.example .env
# 编辑 .env 中的数据库连接和密钥

python scripts/init_db.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

`init_db.py` 会执行数据库迁移，但不会创建默认管理员或默认密码。

### 2. 启动前端

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5175
```

首次访问 `http://localhost:5175/login` 时，页面会要求创建首个管理员。创建成功后，公开管理员创建入口自动关闭。

升级旧版本时，应先重新运行：

```bash
cd backend
python scripts/init_db.py
```

## 环境变量

| 变量 | 说明 |
|------|------|
| `DATABASE_URL` | MySQL 数据库连接 |
| `APP_SECRET_KEY` | 用于敏感配置和登录令牌加密的 Fernet 密钥 |
| `CORS_ORIGINS` | 允许访问后端的前端地址 |
| `SCHEDULER_ENABLED` | 是否启动后台定时任务 |
| `REDIS_ENABLED` | 是否启用 Redis 共享实时缓存。`false` 时使用进程内存 |
| `REDIS_URL` | Redis URL，支持 `redis://` 和 `rediss://` |
| `REDIS_KEY_PREFIX` | Redis Key 命名空间，默认 `today-highlights` |
| `REDIS_SOCKET_TIMEOUT_SECONDS` | Redis 连接超时秒数，默认 1.0 |
| `REDIS_LOCK_TTL_SECONDS` | 分布式刷新锁 TTL 秒数，默认 45 |
| `REDIS_RETRY_INTERVAL_SECONDS` | Redis 恢复重试间隔秒数，默认 30 |

Redis 故障时自动降级为进程内存缓存，不会阻止应用启动。`/health` 端点返回 `{"cache": "redis"|"memory-fallback"|"memory-disabled"}`。

| `LOG_DIR` | 日志文件目录，默认 `logs` |
| `LOG_LEVEL` | 日志级别：`DEBUG`/`INFO`/`WARNING`/`ERROR`，默认 `INFO` |
| `LOG_ROTATION` | 滚动策略：`daily`（每天）或 `hourly`（每小时），默认 `daily` |
| `LOG_RETENTION_DAYS` | 日志保留天数，默认 14 |
| `LOG_MAX_MESSAGE_LENGTH` | 单条日志最大字符数，超长截断，默认 4000 |
| `LOG_CONSOLE_ENABLED` | 是否同时输出到控制台，默认 `true` |
| `LOG_SLOW_REQUEST_MS` | 慢请求阈值（毫秒），超时标记 `slow=true`，默认 2000 |
| `LOG_ACCESS_EXCLUDE_PATHS` | 逗号分隔的排除路径（如 `/health`），这些路径不写入 access 日志 |
| `LOG_TRUST_PROXY_HEADERS` | 是否信任 `X-Forwarded-For`，Nginx 反代时设为 `true` |
| `LOG_DETAIL_CRAWLER` | 是否记录脱敏后的完整上游 URL，默认 `true` |
| `LOG_DETAIL_AI` | 是否记录 AI 输入输出规模和 Token 用量，默认 `true` |
| `LOG_RESPONSE_PREVIEW_CHARS` | 上游失败响应摘要长度，范围 0–2000，默认 500 |
| `LOG_URL_QUERY_MODE` | URL 查询参数模式：`safe` 保留普通值并隐藏敏感值，`keys` 只保留参数名 |

**生产部署命令**（宝塔面板）：
```bash
cd /root/projects/daily_highlights/TodayHighlights/backend
mkdir -p logs
chmod 750 logs
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

**运维命令**：
```bash
tail -f logs/access.log        # HTTP 请求（含 request_id, status, duration）
tail -f logs/application.log   # 业务事件（crawler/ai/scheduler/cache）
tail -f logs/error.log         # 异常（自动关联 request_id）
grep -B1 -A3 'upstream.failed' logs/application.log
grep -B1 'job_id=43766' logs/application.log
grep -B1 'source_name="指数行情"' logs/application.log
grep -B1 'ai_job_id=829' logs/application.log
grep -B1 'request=0edcd5f9' logs/access.log logs/error.log
```

日志中的业务对象始终同时包含名称和 ID，无需再查询数据库才能理解。上游 URL
会完整记录，但 API Key、Token、签名、Cookie、数据库密码等敏感值自动替换为
`[REDACTED]`。失败响应只记录脱敏且截断后的摘要；AI Prompt 和完整模型响应不会
写入日志文件。

生成 `APP_SECRET_KEY`：

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## 页面与模块

### 公共页面

- `/`：综合摘要看板
- `/topics/stocks`：股票主题看板
- `/topics/football`：足球主题看板
- `/topics/ai`：AI 主题看板

### 管理后台

- `/admin/layout`：页面方块和布局配置
- `/admin/sources`：数据连接器配置
- `/admin/jobs`：同步任务和错误日志
- `/admin/topics`：主题管理
- `/admin/settings`：AI 模型配置
- `/admin/ai-prompts`：提示词模板
- `/admin/ai-ops`：AI 任务和 Token 用量
- `/admin/users`：用户管理

## 数据接入

系统通过 Adapter 接口隔离不同数据来源，并将数据转换成统一结构。推荐优先使用：

- 已获得授权的正式 API
- 明确允许程序化访问的开放数据
- RSS、Atom 等标准订阅协议
- 用户拥有使用权的本地或内部数据

新增连接器时，应同时实现超时、限速、失败重试、缓存和来源标识，并遵守数据提供方的服务协议、访问规则及适用法律。

## 合规说明

本项目仅提供信息聚合、数据处理和看板展示的技术框架，不附带任何第三方数据的访问权或再分发许可。

部署者需要自行确认所接入数据的授权范围、服务协议、知识产权、个人信息处理要求和展示权限。请勿绕过登录、验证码、访问控制、付费限制或其他技术保护措施，也不要采集、存储或公开无合法处理依据的数据。

## 运行测试

```bash
cd backend
APP_SECRET_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= python3 -m pytest tests/ -v

cd frontend
npx vitest run
```
