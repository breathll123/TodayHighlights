# API 接口文档

> Base URL: `http://localhost:8000`  
> 所有管理后台 API (`/api/admin/*`) 需要 Bearer Token 认证，公开 API 无需认证

---

## 1. 公开 API

### GET /health

健康检查。

```
GET /health
```

**响应：**
```json
{"status": "ok"}
```

---

### GET /api/public/topics

获取启用的公开话题列表。

```
GET /api/public/topics
```

**响应（1-2条）：**
```json
[
  {"id": 1, "name": "股票", "slug": "stocks", "sort_order": 1},
  {"id": 2, "name": "AI", "slug": "ai", "sort_order": 0}
]
```

---

### GET /api/public/highlights

获取已发布的看点（不含隐藏）。

```
GET /api/public/highlights
```

**响应（1-2条）：**
```json
[
  {
    "id": 1, "title": "金融资本的“平均利润”法则",
    "summary": "从长鑫科技的千亿逆袭，看金融与科技的共生演进...",
    "related_symbols_json": [], "tags_json": ["深度"], "score": 85,
    "is_pinned": false, "created_at": "2026-05-22T12:32:38"
  }
]
```

---

### GET /api/public/pages/{route}/blocks

获取指定页面已发布的区块及聚合数据。`route` 需 URL 编码（`/` → `%2F`）。

```
GET /api/public/pages/%2F/blocks        ← 首页
GET /api/public/pages/topics%2Fstocks/blocks  ← 股票页
```

**响应（1-2条）：**
```json
{
  "blocks": [
    {
      "id": 1, "title": "今日热股", "source_type": "hot_stocks",
      "display_style": "list", "display_count": 10,
      "col_span": 4, "row_span": 1, "grid_x": 0, "grid_y": 0,
      "data": [
        {
          "title": "京东方A", "summary": "SZ000725 热度43157", "url": "https://xueqiu.com/S/SZ000725",
          "symbols": ["SZ000725"], "score": 43157, "percent": 10.02,
          "current": 5.16, "source": "hot_stocks"
        }
      ]
    },
    {
      "id": 2, "title": "深度文章", "source_type": "topic",
      "display_style": "card", "display_count": 5,
      "col_span": 2, "row_span": 2, "grid_x": 0, "grid_y": 1,
      "data": [
        {
          "id": 90, "title": "随想278 必选消费品能对抗通胀吗？",
          "summary": "继续通胀的话题聊。5月21日凌晨公布的美联储的FOMC纪要...",
          "url": "https://xueqiu.com/7297620365/390305487",
          "related_symbols_json": [], "tags_json": ["雪球"],
          "score": 75, "is_pinned": false, "created_at": "2026-05-22T20:09:06"
        }
      ]
    }
  ]
}
```

**返回 `data` 的字段随 `source_type` 不同：**

| source_type | data 字段 |
|-------------|-----------|
| `topic` | `id, title, summary, url, score, is_pinned, tags_json, related_symbols_json, created_at` |
| `hot_stocks` | `title, summary, url, symbols[], score, percent, current` |
| `hot_events` | `title, summary, tags[], score` |
| `screener` | `title, summary, url, symbols[], score, percent` |
| `eastmoney_sectors` | `title, summary, url, symbols[], score, percent` |
| `eastmoney_gainers` | `title, summary, url, symbols[], score, percent, current` |

---

## 2. 认证

### POST /api/admin/login

管理员登录，获取 token。

```
POST /api/admin/login
Content-Type: application/json

{"password": "admin123"}
```

**响应：**
```json
{"token": "<encrypted-token-string>"}
```

**注意：** 默认密码 `admin123`，存储在 `app_settings` 表的 `admin.password` 键中。所有后续管理 API 需要在 Header 中携带 `Authorization: Bearer <token>`。

---

## 3. 管理后台 API（需认证）

所有以下接口 Header：`Authorization: Bearer <token>`

---

### 数据源管理

#### GET /api/admin/sources

获取所有数据源。

```json
[
  {
    "id": 1, "name": "雪球自选", "site": "xueqiu",
    "entry_url": "https://xueqiu.com/v4/statuses/public_timeline_by_category.json",
    "topic_id": 1, "enabled": true, "crawl_interval_minutes": 60,
    "last_crawled_at": "2026-05-22T20:09:06", "has_cookie": true
  }
]
```

#### POST /api/admin/sources

创建数据源。

```json
POST /api/admin/sources
{
  "topic_id": 1, "site": "xueqiu", "name": "雪球自选",
  "entry_url": "https://xueqiu.com/v4/statuses/public_timeline_by_category.json",
  "cookie": "xq_a_token=xxx; u=12345; ...", "enabled": true, "crawl_interval_minutes": 60
}
```

**响应：** 同 GET 单条格式（`has_cookie: true` 表示 Cookie 已配置但不返回原文）

#### POST /api/admin/sources/{id}/crawl

手动触发一次爬取。

```
POST /api/admin/sources/1/crawl
```

**响应：**
```json
{"id": 10, "status": "success", "items_found": 20, "items_saved": 20}
```

---

### 任务日志

#### GET /api/admin/jobs

获取最近 50 条爬取任务。

```json
[
  {
    "id": 10, "source_id": 1, "trigger_type": "manual",
    "status": "success", "items_found": 20, "items_saved": 20,
    "error_message": "", "log_excerpt": "",
    "started_at": "2026-05-22T20:09:06", "finished_at": "2026-05-22T20:09:08"
  }
]
```

---

### 看点审核

#### PATCH /api/admin/highlights/{id}

编辑看点（标题、摘要、置顶、隐藏）。

```
PATCH /api/admin/highlights/1
{"title": "新标题", "summary": "新摘要", "is_pinned": true, "is_hidden": false}
```

**响应：**
```json
{"id": 1, "review_status": "reviewed"}
```

---

### 话题管理

#### GET /api/admin/topics

```json
[
  {"id": 1, "name": "股票", "slug": "stocks", "sort_order": 1, "enabled": true},
  {"id": 2, "name": "AI", "slug": "ai", "sort_order": 0, "enabled": true}
]
```

#### POST /api/admin/topics

```
POST /api/admin/topics
{"name": "AI", "slug": "ai", "sort_order": 0, "enabled": true}
```

#### PUT /api/admin/topics/{id}

```
PUT /api/admin/topics/2
{"name": "AI", "slug": "ai", "sort_order": 1, "enabled": true}
```

#### DELETE /api/admin/topics/{id}

```
DELETE /api/admin/topics/2
```

**响应：** `{"deleted": true}`

---

### 模型设置

#### GET /api/admin/settings/model

```json
{"base_url": "https://api.openai.com/v1", "model": "gpt-4o", "has_api_key": true}
```

#### PUT /api/admin/settings/model

```
PUT /api/admin/settings/model
{"base_url": "https://api.openai.com/v1", "api_key": "sk-xxx", "model": "gpt-4o"}
```

**响应：**
```json
{"saved": true, "has_api_key": true}
```

**注意：** `api_key` 留空表示不修改已存储的密钥。`has_api_key` 只返回是否配置，不返回原文。

---

### 页面区块管理

#### GET /api/admin/blocks

获取所有区块（含 draft 和 published）。

```json
[
  {
    "id": 1, "page_route": "/", "title": "今日热股", "source_type": "hot_stocks",
    "source_config": {"type": 10}, "display_style": "list", "display_count": 10,
    "sort_by": "created_at", "enabled": true,
    "block_key": "abc-def-123",
    "col_span": 4, "row_span": 1, "grid_x": 0, "grid_y": 0,
    "status": "draft",
    "created_at": "2026-05-23T...", "updated_at": "2026-05-23T..."
  }
]
```

#### POST /api/admin/blocks

创建区块。

```
POST /api/admin/blocks
{
  "page_route": "/", "title": "热门话题", "source_type": "hot_events",
  "source_config": {}, "block_key": "uuid-from-frontend",
  "col_span": 2, "row_span": 1, "grid_x": 0, "grid_y": 1,
  "display_style": "card", "display_count": 5,
  "sort_by": "created_at", "enabled": true,
  "sort_order": 0, "status": "draft"
}
```

#### PUT /api/admin/blocks/{id}

更新区块（只传需要改的字段）。

```
PUT /api/admin/blocks/1
{"title": "今日话题", "display_style": "list", "grid_x": 1}
```

#### DELETE /api/admin/blocks/{id}

```
DELETE /api/admin/blocks/1
```

**响应：** `{"deleted": true}`

#### PATCH /api/admin/blocks/reorder

批量更新排序。

```
PATCH /api/admin/blocks/reorder
{"items": [{"id": 1, "sort_order": 0}, {"id": 2, "sort_order": 1}]}
```

**响应：** `{"updated": true}`

---

### 页面发布

#### POST /api/admin/pages/{route}/publish

将 draft 区块发布为 published（事务式：先删旧 published，再复制 draft）。

```
POST /api/admin/pages/%2F/publish
```

**响应：**
```json
{"published": true, "blocks": 5}
```

---

## 4. 认证说明

| 接口组 | 前缀 | 需要认证 |
|--------|------|----------|
| 健康检查 | `/health` | 否 |
| 公开 API | `/api/public/*` | 否 |
| 登录 | `/api/admin/login` | 否 |
| 管理后台 | `/api/admin/*`（除 login） | 是，Bearer Token |

**Token 获取：**
1. `POST /api/admin/login` 传入密码
2. 返回 token，有效期 7 天
3. 后续请求 Header 加入 `Authorization: Bearer <token>`

**Token 存储：** 前端存 `localStorage.admin_token`，Axios 拦截器自动附加。

---

## 5. ER 图

```
topics ──< sources ──< crawl_jobs
   │           │
   │           └──< raw_items ──< highlights
   │
   └──< highlights
   │
   └──< page_blocks (draft / published)

app_settings (key-value, 独立)
```

---

## 6. 完整端点列表

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/health` | 健康检查 | - |
| GET | `/api/public/topics` | 公开话题 | - |
| GET | `/api/public/highlights` | 公开看点 | - |
| GET | `/api/public/pages/{route}/blocks` | 页面区块+数据 | - |
| POST | `/api/admin/login` | 管理员登录 | - |
| GET | `/api/admin/sources` | 数据源列表 | Bearer |
| POST | `/api/admin/sources` | 创建数据源 | Bearer |
| POST | `/api/admin/sources/{id}/crawl` | 触发爬取 | Bearer |
| GET | `/api/admin/jobs` | 任务日志 | Bearer |
| PATCH | `/api/admin/highlights/{id}` | 编辑看点 | Bearer |
| GET | `/api/admin/topics` | 话题列表 | Bearer |
| POST | `/api/admin/topics` | 创建话题 | Bearer |
| PUT | `/api/admin/topics/{id}` | 编辑话题 | Bearer |
| DELETE | `/api/admin/topics/{id}` | 删除话题 | Bearer |
| GET | `/api/admin/settings/model` | 模型设置 | Bearer |
| PUT | `/api/admin/settings/model` | 保存模型设置 | Bearer |
| GET | `/api/admin/blocks` | 区块列表 | Bearer |
| POST | `/api/admin/blocks` | 创建区块 | Bearer |
| PUT | `/api/admin/blocks/{id}` | 编辑区块 | Bearer |
| DELETE | `/api/admin/blocks/{id}` | 删除区块 | Bearer |
| PATCH | `/api/admin/blocks/reorder` | 区块排序 | Bearer |
| POST | `/api/admin/pages/{route}/publish` | 发布页面 | Bearer |
