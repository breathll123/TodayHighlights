# DataFlow — 多源实时信息看板

聚合雪球、东方财富、同花顺三大财经平台数据，以可定制的方块看板形式展示。支持沪深港美股热度、概念/行业板块、龙虎榜、财经快讯等多维度数据。

## 技术栈

**后端:** FastAPI + SQLAlchemy 2.0 + MySQL + APScheduler
**前端:** React 18 + Vite + TypeScript + Tailwind CSS + shadcn/ui + framer-motion
**采集:** httpx + Playwright (龙虎榜 Cookie 刷新)

## 架构

```
采集层 (adapters/)  →  存储层 (raw_items/highlights)  →  展示层 (blocks/)
─────────────────      ─────────────────────────         ────────────────
雪球 (xueqiu)          raw_items — 原始采集数据          方块编辑器 (CanvasEditor)
东方财富 (eastmoney)    highlights — AI 摘要内容         卡片/列表/时间线
同花顺 (tonghuashun)   page_blocks — 看板布局配置        动态列 + 排序
```

每个方块独立配置数据来源、展示样式、显示字段和排序方式。

## 快速开始

### 后端

```bash
cd backend
conda activate daily_highlights
cp .env.example .env  # 编辑数据库连接和密钥
uvicorn app.main:app --reload
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

### 环境变量 (`backend/.env`)

| 变量 | 说明 |
|------|------|
| `DATABASE_URL` | MySQL 连接 (如 `mysql+pymysql://root:pass@127.0.0.1:3306/daily_highlights`) |
| `APP_SECRET_KEY` | Fernet 加密密钥，`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `CORS_ORIGINS` | 前端地址，默认 `http://localhost:5173` |
| `SCHEDULER_ENABLED` | 是否启用定时爬取，默认 `true` |
| `EASTMONEY_PROXY` | 可选 HTTP 代理 (如 `http://127.0.0.1:7890`) |

## 数据源

| 来源 | 数据类型 |
|------|----------|
| 雪球 | 热门话题、热门股票、沪深/港股/美股热度榜、涨跌幅榜 |
| 东方财富 | 概念板块、行业板块、指数行情、主力资金、A股公告、龙虎榜 |
| 同花顺 | 财经快讯（时间线展示） |
| 本地 | AI 摘要看点和原始数据源 |

## 管理后台

访问 `/admin/layout` 进入看板编辑器：
- 画布拖拽编辑方块布局
- 每个方块独立配置数据来源、展示样式（卡片/列表/时间线）、显示字段、排序方式
- 草稿-发布工作流，支持多页面（摘要页、股票页）
- `/admin/sources` 管理数据源（添加/编辑 Cookie、触发手动爬取）
- `/admin/jobs` 查看分页任务日志（含错误原因展开）
- `/admin/topics` 管理话题分类

## 数据采集

- 定时调度器每分钟轮询，按 Source 配置的间隔触发爬取
- 东方财富 push2 API 主备域名自动切换 (`push2.eastmoney.com` → `push2delay.eastmoney.com`)
- 龙虎榜通过 Playwright 自动获取 Session Cookie（无需登录）
- 采集数据统一存入 `raw_items` 表，看板从 DB 读取

## 运行测试

```bash
cd backend && APP_SECRET_KEY=test-key python3 -m pytest tests/ -v
cd frontend && npx vitest run
```

## 文档

- [API 接口文档](docs/api-reference.md) — 完整的端点列表和请求/响应示例
- [数据源接口参考](docs/sources-api-reference.md) — 各数据源 API 地址、参数和字段映射
- [多垂类扩展设计](docs/design-vertical-expansion-20260527.md) — AI/足球垂类扩展方案
