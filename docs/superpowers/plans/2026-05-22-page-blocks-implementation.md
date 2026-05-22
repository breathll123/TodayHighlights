# 前端模块管理系统 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 `page_blocks` 数据库驱动的前端模块管理系统，升级前端技术栈到 Tailwind + shadcn/ui + Axios。

**Architecture:** 后端新增 `page_blocks` 表 + CRUD API + 数据聚合公开 API；前端升级为 Tailwind CSS v3 + shadcn/ui 组件库，新增 `/admin/layout` 管理页面，公开页改为 `PageRenderer` 动态渲染。

**Tech Stack:** Python FastAPI + SQLAlchemy + Alembic；React 18 + TypeScript + Tailwind CSS v3 + shadcn/ui + Axios + TanStack Query + next-themes + sonner + framer-motion + Lucide React

---

## 文件结构

```
backend/
  migrations/versions/20260522_0002_page_blocks.py  ← 新建迁移
  app/
    models/entities.py       ← 添加 PageBlock 模型
    schemas/admin.py         ← 添加 BlockCreate/BlockUpdate/BlockRead schema
    schemas/public.py        ← 添加 PageBlocksResponse schema
    api/admin.py             ← 添加 blocks CRUD 路由
    api/public.py            ← 添加 GET /pages/{route}/blocks
    services/blocks.py       ← 新建：区块数据聚合服务
    main.py                  ← 注册新路由

frontend/
  src/
    api/
      client.ts              ← 改用 Axios
      types.ts               ← 添加 Block 类型
    components/
      ui/                    ← shadcn/ui 组件（button, card, dialog, input, select, switch, tabs, separator, scroll-area）
      layout/
        Navbar.tsx            ← 改写为 Tailwind
        BlockCard.tsx         ← 新建：公开页面区块卡片
      admin/
        AdminSidebar.tsx      ← 新建：管理后台侧栏
        BlockEditor.tsx       ← 新建：区块编辑 Dialog
        SortableBlockItem.tsx ← 新建：拖拽排序项
    pages/
      SummaryPage.tsx         ← 改为 PageRenderer
      StockTopicPage.tsx      ← 改为 PageRenderer
      AdminSourcesPage.tsx    ← 改写为 Tailwind + shadcn/ui
      AdminJobsPage.tsx       ← 改写
      AdminHighlightsPage.tsx ← 改写
      AdminSettingsPage.tsx   ← 改写
      AdminLayoutPage.tsx     ← 新建：页面布局管理
    hooks/
      use-page-blocks.ts      ← 新建
    lib/
      utils.ts                ← 新建：clsx + twMerge
    styles/
      globals.css             ← Tailwind + CSS Variables
```

---

### Task 1: 前端技术栈初始化

- [ ] **Step 1: 安装新依赖**

```bash
cd frontend
npm install tailwindcss@3 postcss autoprefixer clsx tailwind-merge class-variance-authority
npm install axios @tanstack/react-query react-router-dom
npm install lucide-react next-themes sonner framer-motion
npm install recharts react-markdown remark-gfm
npm install -D @types/react @types/react-dom
```

运行 `npx tailwindcss init -p` 生成 `tailwind.config.js` 和 `postcss.config.js`。

- [ ] **Step 2: 配置 Tailwind**

创建 `frontend/tailwind.config.js`：

```js
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        card: "hsl(var(--card))",
        primary: "hsl(var(--primary))",
        muted: "hsl(var(--muted))",
        border: "hsl(var(--border))",
      },
    },
  },
  plugins: [],
};
```

- [ ] **Step 3: 初始化 shadcn/ui**

创建 `frontend/components.json`：

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "default",
  "rsc": false,
  "tsx": true,
  "tailwind": {
    "config": "tailwind.config.js",
    "css": "src/styles/globals.css",
    "baseColor": "slate",
    "cssVariables": true
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils"
  }
}
```

更新 `frontend/tsconfig.json`，在 `compilerOptions` 中添加：

```json
"baseUrl": ".",
"paths": { "@/*": ["./src/*"] }
```

更新 `frontend/vite.config.ts`，在 `defineConfig` 中添加路径 alias：

```ts
import path from "path";
// ...
resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
```

- [ ] **Step 4: 创建全局样式**

创建 `frontend/src/styles/globals.css`：

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 222.2 84% 4.9%;
    --card: 0 0% 100%;
    --primary: 222.2 47.4% 11.2%;
    --muted: 210 40% 96.1%;
    --border: 214.3 31.8% 91.4%;
    --radius: 0.5rem;
  }
  .dark {
    --background: 222.2 84% 4.9%;
    --foreground: 210 40% 98%;
    --card: 222.2 84% 4.9%;
    --primary: 210 40% 98%;
    --muted: 217.2 32.6% 17.5%;
    --border: 217.2 32.6% 17.5%;
  }
  * { @apply border-border; }
  body { @apply bg-background text-foreground; }
}
```

- [ ] **Step 5: 创建 utils 工具函数**

创建 `frontend/src/lib/utils.ts`：

```ts
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

- [ ] **Step 6: 安装 shadcn/ui 组件**

运行以下命令逐个添加组件：

```bash
npx shadcn-ui@latest add button card dialog input select switch tabs separator scroll-area dropdown-menu
```

这些命令会在 `frontend/src/components/ui/` 下生成对应的 `.tsx` 文件。

- [ ] **Step 7: 配置 Axios 实例**

创建 `frontend/src/api/client.ts`（替换旧的 fetch 实现）：

```ts
import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE ?? "http://localhost:8000",
  timeout: 15000,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const message = err.response?.data?.detail ?? err.message;
    return Promise.reject(new Error(message));
  }
);

export default api;
```

- [ ] **Step 8: 添加 Axios API 函数**

重写 `frontend/src/api/client.ts`，将所有 `fetch` + `getJson/postJson/putJson/patchJson/deleteJson` 改为 Axios：

```ts
import api from "./client";
import type { Highlight, Topic, Source, CrawlJob, ModelSettings, Block } from "./types";

export const fetchTopics = () => api.get<Topic[]>("/api/public/topics").then(r => r.data);
export const fetchHighlights = () => api.get<Highlight[]>("/api/public/highlights").then(r => r.data);
export const fetchSources = () => api.get<Source[]>("/api/admin/sources").then(r => r.data);
export const createSource = (data: {...}) => api.post<Source>("/api/admin/sources", data).then(r => r.data);
export const triggerCrawl = (id: number) => api.post(`/api/admin/sources/${id}/crawl`).then(r => r.data);
export const deleteSource = (id: number) => api.delete(`/api/admin/sources/${id}`).then(r => r.data);
export const fetchJobs = () => api.get<CrawlJob[]>("/api/admin/jobs").then(r => r.data);
export const fetchModelSettings = () => api.get<ModelSettings>("/api/admin/settings/model").then(r => r.data);
export const saveModelSettings = (data: {...}) => api.put("/api/admin/settings/model", data).then(r => r.data);
export const updateHighlight = (id: number, data: {...}) => api.patch(`/api/admin/highlights/${id}`, data).then(r => r.data);
export const deleteHighlight = (id: number) => api.delete(`/api/admin/highlights/${id}`).then(r => r.data);
// 新增
export const fetchPageBlocks = (route: string) => api.get(`/api/public/pages/${route}/blocks`).then(r => r.data);
export const fetchBlocks = () => api.get<Block[]>("/api/admin/blocks").then(r => r.data);
export const createBlock = (data: Omit<Block, "id">) => api.post<Block>("/api/admin/blocks", data).then(r => r.data);
export const updateBlock = (id: number, data: Partial<Block>) => api.put<Block>(`/api/admin/blocks/${id}`, data).then(r => r.data);
export const deleteBlock = (id: number) => api.delete(`/api/admin/blocks/${id}`).then(r => r.data);
export const reorderBlocks = (items: { id: number; sort_order: number }[]) => api.patch("/api/admin/blocks/reorder", { items }).then(r => r.data);
```

- [ ] **Step 9: 更新 TypeScript 类型**

更新 `frontend/src/api/types.ts`，添加 Block 类型：

```ts
export interface Block {
  id: number;
  page_route: string;
  title: string;
  sort_order: number;
  source_type: "topic" | "search" | "hot_stocks" | "hot_events" | "screener";
  source_config: Record<string, unknown>;
  display_style: "card" | "list";
  display_count: number;
  sort_by: "score" | "created_at";
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface PageBlocksResponse {
  blocks: (Block & { data: unknown[] })[];
}
```

- [ ] **Step 10: 添加主题 Provider**

更新 `frontend/src/main.tsx`：

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { ThemeProvider } from "next-themes";
import { Toaster } from "sonner";
import App from "./App";
import "./styles/globals.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
      <App />
      <Toaster position="top-right" richColors />
    </ThemeProvider>
  </React.StrictMode>
);
```

- [ ] **Step 11: 验证前端编译**

```bash
cd frontend && npm run build
```

预期：TypeScript 编译 + Vite 构建成功。

- [ ] **Step 12: 提交**

```bash
git add frontend
git commit -m "feat: upgrade frontend stack to Tailwind + shadcn/ui + Axios"
```

---

### Task 2: 后端 page_blocks 迁移和模型

**Files:**
- Create: `backend/migrations/versions/20260522_0002_page_blocks.py`
- Modify: `backend/app/models/entities.py:460`

- [ ] **Step 1: 编写模型测试**

创建 `backend/tests/test_page_blocks.py`：

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models.entities import PageBlock


def test_page_block_crud() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        block = PageBlock(
            page_route="/",
            title="今日热股",
            sort_order=0,
            source_type="hot_stocks",
            source_config={"type": 10},
            display_count=5,
        )
        session.add(block)
        session.commit()

        saved = session.query(PageBlock).one()
        assert saved.title == "今日热股"
        assert saved.source_type == "hot_stocks"
        assert saved.source_config == {"type": 10}
        assert saved.enabled is True
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && APP_SECRET_KEY=test-key /Users/lws/opt/anaconda3/envs/daily_highlights/bin/pytest tests/test_page_blocks.py -v
```

预期：`ImportError: cannot import name 'PageBlock'`

- [ ] **Step 3: 添加 PageBlock 模型**

在 `backend/app/models/entities.py` 末尾添加：

```python
class PageBlock(TimestampMixin, Base):
    __tablename__ = "page_blocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    page_route: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    display_style: Mapped[str] = mapped_column(String(40), default="card", nullable=False)
    display_count: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    sort_by: Mapped[str] = mapped_column(String(40), default="created_at", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
```

更新 `backend/app/models/__init__.py`，添加 `PageBlock` 到导出列表。

- [ ] **Step 4: 创建迁移文件**

创建 `backend/migrations/versions/20260522_0002_page_blocks.py`：

```python
"""page_blocks

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-22
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "page_blocks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("page_route", sa.String(80), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("source_config", sa.JSON(), nullable=False),
        sa.Column("display_style", sa.String(40), nullable=False, server_default="card"),
        sa.Column("display_count", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("sort_by", sa.String(40), nullable=False, server_default="created_at"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_page_blocks_route_sort", "page_blocks", ["page_route", "sort_order"])


def downgrade() -> None:
    op.drop_index("ix_page_blocks_route_sort")
    op.drop_table("page_blocks")
```

- [ ] **Step 5: 运行迁移和测试**

```bash
cd backend
PYTHONPATH=. alembic upgrade head
APP_SECRET_KEY=test-key /Users/lws/opt/anaconda3/envs/daily_highlights/bin/pytest tests/test_page_blocks.py -v
```

预期：`1 passed`

- [ ] **Step 6: 提交**

```bash
git add backend
git commit -m "feat: add page_blocks model and migration"
```

---

### Task 3: 后端 page_blocks API

**Files:**
- Create: `backend/app/services/blocks.py`
- Modify: `backend/app/schemas/admin.py`
- Modify: `backend/app/schemas/public.py`
- Modify: `backend/app/api/admin.py`
- Modify: `backend/app/api/public.py`
- Create: `backend/tests/test_blocks_api.py`

- [ ] **Step 1: 添加 Schema**

在 `backend/app/schemas/admin.py` 末尾添加：

```python
class BlockCreate(BaseModel):
    page_route: str
    title: str
    sort_order: int = 0
    source_type: str
    source_config: dict[str, Any]
    display_style: str = "card"
    display_count: int = 5
    sort_by: str = "created_at"
    enabled: bool = True


class BlockUpdate(BaseModel):
    page_route: str | None = None
    title: str | None = None
    sort_order: int | None = None
    source_type: str | None = None
    source_config: dict[str, Any] | None = None
    display_style: str | None = None
    display_count: int | None = None
    sort_by: str | None = None
    enabled: bool | None = None


class BlockRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    page_route: str
    title: str
    sort_order: int
    source_type: str
    source_config: dict[str, Any]
    display_style: str
    display_count: int
    sort_by: str
    enabled: bool
    created_at: datetime
    updated_at: datetime


class ReorderRequest(BaseModel):
    items: list[dict[str, int]]
```

在 `backend/app/schemas/public.py` 末尾添加：

```python
class PageBlocksResponse(BaseModel):
    blocks: list[dict[str, Any]]
```

- [ ] **Step 2: 编写 API 测试**

创建 `backend/tests/test_blocks_api.py`：

```python
from fastapi.testclient import TestClient

from app.main import app


def test_list_blocks_empty(client: TestClient) -> None:
    response = client.get("/api/admin/blocks")
    assert response.status_code == 200
    assert response.json() == []


def test_create_and_list_blocks(client: TestClient) -> None:
    payload = {
        "page_route": "/",
        "title": "今日热股",
        "source_type": "hot_stocks",
        "source_config": {"type": 10},
        "display_count": 5,
    }
    resp = client.post("/api/admin/blocks", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "今日热股"
    assert data["source_type"] == "hot_stocks"

    resp2 = client.get("/api/admin/blocks")
    assert len(resp2.json()) == 1


def test_update_block(client: TestClient) -> None:
    payload = {"page_route": "/", "title": "测试", "source_type": "topic", "source_config": {"topic_id": 1}}
    resp = client.post("/api/admin/blocks", json=payload)
    block_id = resp.json()["id"]

    resp2 = client.put(f"/api/admin/blocks/{block_id}", json={"title": "已修改"})
    assert resp2.json()["title"] == "已修改"


def test_delete_block(client: TestClient) -> None:
    payload = {"page_route": "/", "title": "测试", "source_type": "topic", "source_config": {"topic_id": 1}}
    resp = client.post("/api/admin/blocks", json=payload)
    block_id = resp.json()["id"]

    resp2 = client.delete(f"/api/admin/blocks/{block_id}")
    assert resp2.json()["deleted"] is True


def test_reorder_blocks(client: TestClient) -> None:
    for i in range(3):
        client.post("/api/admin/blocks", json={"page_route": "/", "title": f"区块{i}", "source_type": "topic", "source_config": {"topic_id": 1}, "sort_order": i})

    resp = client.patch("/api/admin/blocks/reorder", json={"items": [{"id": 1, "sort_order": 2}, {"id": 2, "sort_order": 1}, {"id": 3, "sort_order": 0}]})
    assert resp.status_code == 200

    blocks = client.get("/api/admin/blocks").json()
    orders = [b["sort_order"] for b in blocks]
    assert orders == [2, 1, 0]


def test_public_page_blocks(client: TestClient) -> None:
    client.post("/api/admin/blocks", json={"page_route": "/", "title": "热股", "source_type": "hot_stocks", "source_config": {"type": 10}, "enabled": True})
    client.post("/api/admin/blocks", json={"page_route": "/", "title": "隐藏区块", "source_type": "topic", "source_config": {"topic_id": 1}, "enabled": False})

    resp = client.get("/api/public/pages/%2F/blocks")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["blocks"]) == 1
    assert data["blocks"][0]["title"] == "热股"
```

- [ ] **Step 3: 实现 blocks 服务**

创建 `backend/app/services/blocks.py`：

```python
from app.core.database import SessionLocal
from app.models.entities import Highlight, PageBlock
from sqlalchemy import select
from sqlalchemy.orm import Session


def resolve_block_data(session: Session, block: PageBlock) -> list[dict]:
    source_type = block.source_type
    config = block.source_config or {}
    limit = block.display_count

    if source_type == "topic":
        topic_id = config.get("topic_id", 1)
        stmt = (
            select(Highlight)
            .where(Highlight.topic_id == topic_id, Highlight.is_hidden.is_(False))
            .order_by(Highlight.is_pinned.desc(), Highlight.score.desc(), Highlight.created_at.desc())
            .limit(limit)
        )
        highlights = session.scalars(stmt).all()
        return [
            {
                "id": h.id,
                "title": h.title,
                "summary": h.summary,
                "related_symbols_json": h.related_symbols_json,
                "tags_json": h.tags_json,
                "score": h.score,
                "is_pinned": h.is_pinned,
                "created_at": h.created_at.isoformat() if h.created_at else None,
            }
            for h in highlights
        ]

    # hot_stocks / hot_events / search / screener → 后续任务实现（当前返回空数组）
    return []


def get_page_blocks(session: Session, route: str) -> list[dict]:
    stmt = (
        select(PageBlock)
        .where(PageBlock.page_route == route, PageBlock.enabled.is_(True))
        .order_by(PageBlock.sort_order)
    )
    blocks = session.scalars(stmt).all()
    result = []
    for block in blocks:
        item = {
            "id": block.id,
            "title": block.title,
            "sort_order": block.sort_order,
            "display_style": block.display_style,
            "display_count": block.display_count,
            "source_type": block.source_type,
            "data": resolve_block_data(session, block),
        }
        result.append(item)
    return result
```

- [ ] **Step 4: 实现管理后台 CRUD 路由**

在 `backend/app/api/admin.py` 末尾添加：

```python
from app.models.entities import PageBlock
from app.schemas.admin import BlockCreate, BlockUpdate, BlockRead, ReorderRequest


@router.get("/blocks", response_model=list[BlockRead])
def list_blocks(session: Session = Depends(get_session)) -> list[PageBlock]:
    return list(session.scalars(select(PageBlock).order_by(PageBlock.page_route, PageBlock.sort_order)))


@router.post("/blocks", response_model=BlockRead)
def create_block(payload: BlockCreate, session: Session = Depends(get_session)) -> PageBlock:
    block = PageBlock(**payload.model_dump())
    session.add(block)
    session.commit()
    session.refresh(block)
    return block


@router.put("/blocks/{block_id}", response_model=BlockRead)
def update_block(block_id: int, payload: BlockUpdate, session: Session = Depends(get_session)) -> PageBlock:
    block = session.get(PageBlock, block_id)
    if block is None:
        raise HTTPException(status_code=404, detail="Block not found")
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(block, key, value)
    session.commit()
    session.refresh(block)
    return block


@router.delete("/blocks/{block_id}")
def delete_block(block_id: int, session: Session = Depends(get_session)) -> dict:
    block = session.get(PageBlock, block_id)
    if block is None:
        return {"deleted": False, "reason": "not found"}
    session.delete(block)
    session.commit()
    return {"deleted": True}


@router.patch("/blocks/reorder")
def reorder_blocks(payload: ReorderRequest, session: Session = Depends(get_session)) -> dict:
    for item in payload.items:
        block = session.get(PageBlock, item["id"])
        if block:
            block.sort_order = item["sort_order"]
    session.commit()
    return {"updated": True}
```

- [ ] **Step 5: 添加公开 API 路由**

在 `backend/app/api/public.py` 末尾添加：

```python
from app.services.blocks import get_page_blocks


@router.get("/pages/{route:path}/blocks")
def page_blocks(route: str, session: Session = Depends(get_session)) -> dict:
    route = "/" + route if not route.startswith("/") else route
    blocks = get_page_blocks(session, route)
    return {"blocks": blocks}
```

- [ ] **Step 6: 运行测试**

```bash
cd backend
APP_SECRET_KEY=test-key /Users/lws/opt/anaconda3/envs/daily_highlights/bin/pytest tests/test_blocks_api.py tests/test_page_blocks.py -v
```

预期：`6 passed` (test_page_blocks) + `6 passed` (test_blocks_api) = 全部通过

- [ ] **Step 7: 提交**

```bash
git add backend
git commit -m "feat: add page_blocks CRUD API and public endpoint"
```

---

### Task 4: 管理后台页面改造（Tailwind + shadcn/ui）

**Files:**
- Modify: `frontend/src/components/layout/Navbar.tsx` (新建)
- Modify: `frontend/src/pages/AdminSourcesPage.tsx`
- Modify: `frontend/src/pages/AdminJobsPage.tsx`
- Modify: `frontend/src/pages/AdminHighlightsPage.tsx`
- Modify: `frontend/src/pages/AdminSettingsPage.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 创建 Navbar 组件**

创建 `frontend/src/components/layout/Navbar.tsx`：

```tsx
import { Link, useLocation } from "react-router-dom";
import { Sun, Moon, LayoutDashboard, Newspaper, BarChart3, Settings, FileText, Clock } from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const adminLinks = [
  { href: "/admin/sources", label: "数据源", icon: FileText },
  { href: "/admin/jobs", label: "任务", icon: Clock },
  { href: "/admin/highlights", label: "看点", icon: Newspaper },
  { href: "/admin/layout", label: "布局", icon: LayoutDashboard },
  { href: "/admin/settings", label: "设置", icon: Settings },
];

export function Navbar() {
  const { theme, setTheme } = useTheme();
  const location = useLocation();
  const isAdmin = location.pathname.startsWith("/admin");

  return (
    <header className="sticky top-0 z-50 border-b bg-background/95 backdrop-blur">
      <div className="flex h-14 items-center justify-between px-6 max-w-6xl mx-auto">
        <div className="flex items-center gap-8">
          <Link to="/" className="text-lg font-bold tracking-tight">
            每日看点
          </Link>
          <nav className="flex items-center gap-1">
            <Link
              to="/"
              className={cn("px-3 py-1.5 text-sm rounded-md hover:bg-muted transition-colors", !isAdmin && "bg-muted")}
            >
              摘要
            </Link>
            <Link
              to="/topics/stocks"
              className="px-3 py-1.5 text-sm rounded-md hover:bg-muted transition-colors"
            >
              股票
            </Link>
            <Link
              to="/admin/sources"
              className={cn("px-3 py-1.5 text-sm rounded-md hover:bg-muted transition-colors", isAdmin && "bg-muted")}
            >
              管理
            </Link>
          </nav>
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
        >
          <Sun className="h-4 w-4 rotate-0 scale-100 transition-transform dark:-rotate-90 dark:scale-0" />
          <Moon className="absolute h-4 w-4 rotate-90 scale-0 transition-transform dark:rotate-0 dark:scale-100" />
        </Button>
      </div>
    </header>
  );
}
```

- [ ] **Step 2: 改造 AdminSourcesPage**

重写 `frontend/src/pages/AdminSourcesPage.tsx`，使用 Tailwind + shadcn/ui：

- `import { Button } from "@/components/ui/button"`
- `import { Input } from "@/components/ui/input"`
- 表单改 Tailwind 布局：`<form className="space-y-4 bg-card border rounded-xl p-6 mb-6">`
- `<input>` 改为 `<Input />`
- `<button>` 改为 `<Button>`（变体：`variant="default"` / `variant="destructive"`）
- 表格改 Tailwind：`<table className="w-full text-sm"><thead><tr className="border-b bg-muted/50">...`
- 错误/成功消息用 sonner toast：`import { toast } from "sonner"` → `toast.error(err.message)`

具体改造——保持现有逻辑，只换 UI 组件和样式类名。

- [ ] **Step 3: 改造 AdminJobsPage**

同上，用 Tailwind + shadcn/ui 重写。核心改动：
- 表格行状态用条件 className：`className={j.status === "failed" ? "bg-red-50" : j.status === "success" ? "bg-green-50" : ""}`

- [ ] **Step 4: 改造 AdminHighlightsPage**

同上。Dialog 改用 shadcn/ui 的 `<Dialog>`、`<DialogContent>`、`<DialogHeader>` 组件。

- [ ] **Step 5: 改造 AdminSettingsPage**

同上。

- [ ] **Step 6: 更新 App.tsx 使用新 Navbar**

```tsx
import { Navbar } from "@/components/layout/Navbar";
// ...
return (
  <QueryClientProvider client={queryClient}>
    <BrowserRouter>
      <div className="min-h-screen bg-background">
        <Navbar />
        <main className="max-w-6xl mx-auto px-6 py-8">
          <Routes>...</Routes>
        </main>
      </div>
    </BrowserRouter>
  </QueryClientProvider>
);
```

- [ ] **Step 7: 删除旧样式文件**

```bash
rm frontend/src/styles.css
```

（不再需要，已用 globals.css + Tailwind 替代）

- [ ] **Step 8: 运行构建验证**

```bash
cd frontend && npm run build
```

预期：成功构建，无 TypeScript 错误。

- [ ] **Step 9: 提交**

```bash
git add frontend
git commit -m "feat: migrate admin pages to Tailwind + shadcn/ui"
```

---

### Task 5: 管理后台布局管理页面

**Files:**
- Create: `frontend/src/pages/AdminLayoutPage.tsx`
- Create: `frontend/src/components/admin/BlockEditor.tsx`
- Modify: `frontend/src/App.tsx` ← 添加路由

- [ ] **Step 1: 创建 BlockEditor 组件**

创建 `frontend/src/components/admin/BlockEditor.tsx`：

```tsx
import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import type { Block } from "@/api/types";

interface Props {
  open: boolean;
  block: Block | null;
  onSave: (data: Omit<Block, "id" | "created_at" | "updated_at">) => void;
  onClose: () => void;
}

const defaultForm = { page_route: "/", title: "", source_type: "topic" as const, source_config: {}, display_style: "card" as const, display_count: 5, sort_by: "created_at" as const, enabled: true, sort_order: 0 };

export function BlockEditor({ open, block, onSave, onClose }: Props) {
  const [form, setForm] = useState(defaultForm);

  useEffect(() => {
    if (block) {
      setForm({ page_route: block.page_route, title: block.title, source_type: block.source_type, source_config: block.source_config, display_style: block.display_style, display_count: block.display_count, sort_by: block.sort_by, enabled: block.enabled, sort_order: block.sort_order });
    } else {
      setForm(defaultForm);
    }
  }, [block, open]);

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader><DialogTitle>{block ? "编辑区块" : "添加区块"}</DialogTitle></DialogHeader>
        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label>标题</Label>
            <Input value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} placeholder="今日热股" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>所属页面</Label>
              <Select value={form.page_route} onValueChange={v => setForm({ ...form, page_route: v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="/">摘要页</SelectItem>
                  <SelectItem value="/topics/stocks">股票页</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>数据来源</Label>
              <Select value={form.source_type} onValueChange={v => setForm({ ...form, source_type: v as typeof form.source_type })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="topic">本地看点</SelectItem>
                  <SelectItem value="hot_stocks">热股榜</SelectItem>
                  <SelectItem value="hot_events">热门话题</SelectItem>
                  <SelectItem value="screener">活跃股票</SelectItem>
                  <SelectItem value="search">关键词搜索</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          {/* 动态配置区：根据 source_type 显示不同字段 */}
          {form.source_type === "topic" && (
            <div className="space-y-2">
              <Label>话题 ID</Label>
              <Input type="number" value={String(form.source_config?.topic_id ?? 1)} onChange={e => setForm({ ...form, source_config: { topic_id: +e.target.value } })} />
            </div>
          )}
          {form.source_type === "hot_stocks" && (
            <div className="space-y-2">
              <Label>榜单类型</Label>
              <Select value={String(form.source_config?.type ?? 10)} onValueChange={v => setForm({ ...form, source_config: { type: +v } })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="10">A股热度榜</SelectItem>
                  <SelectItem value="11">美股热度榜</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}
          {form.source_type === "search" && (
            <div className="space-y-2">
              <Label>搜索关键词</Label>
              <Input value={String(form.source_config?.query ?? "")} onChange={e => setForm({ ...form, source_config: { query: e.target.value, count: 20 } })} placeholder="芯片" />
            </div>
          )}
          {form.source_type === "screener" && (
            <div className="space-y-2">
              <Label>排序字段</Label>
              <Select value={String(form.source_config?.order_by ?? "percent")} onValueChange={v => setForm({ ...form, source_config: { order_by: v, size: 20 } })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="percent">涨跌幅</SelectItem>
                  <SelectItem value="turnover_rate">换手率</SelectItem>
                  <SelectItem value="volume">成交量</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>展示条数 ({form.display_count})</Label>
              <Slider value={[form.display_count]} onValueChange={([v]) => setForm({ ...form, display_count: v })} min={1} max={20} step={1} />
            </div>
            <div className="space-y-2">
              <Label>排序方式</Label>
              <Select value={form.sort_by} onValueChange={v => setForm({ ...form, sort_by: v as typeof form.sort_by })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="score">热度</SelectItem>
                  <SelectItem value="created_at">时间</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Switch checked={form.enabled} onCheckedChange={v => setForm({ ...form, enabled: v })} />
            <Label>启用</Label>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>取消</Button>
          <Button onClick={() => onSave(form)}>保存</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 2: 创建 AdminLayoutPage**

创建 `frontend/src/pages/AdminLayoutPage.tsx`：

```tsx
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { GripVertical, Plus, Pencil, Trash2, Eye, EyeOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { BlockEditor } from "@/components/admin/BlockEditor";
import { fetchBlocks, createBlock, updateBlock, deleteBlock } from "@/api/client";
import type { Block } from "@/api/types";
import { toast } from "sonner";

const pages = [
  { route: "/", label: "摘要页" },
  { route: "/topics/stocks", label: "股票页" },
];

export function AdminLayoutPage() {
  const queryClient = useQueryClient();
  const [activePage, setActivePage] = useState("/");
  const [editorOpen, setEditorOpen] = useState(false);
  const [editingBlock, setEditingBlock] = useState<Block | null>(null);

  const { data: blocks = [], isLoading } = useQuery({ queryKey: ["blocks"], queryFn: fetchBlocks });
  const pageBlocks = blocks.filter((b: Block) => b.page_route === activePage).sort((a: Block, b: Block) => a.sort_order - b.sort_order);

  const createMut = useMutation({ mutationFn: createBlock, onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["blocks"] }); setEditorOpen(false); toast.success("区块已添加"); } });
  const updateMut = useMutation({ mutationFn: ({ id, data }: { id: number; data: Partial<Block> }) => updateBlock(id, data), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["blocks"] }); setEditorOpen(false); setEditingBlock(null); toast.success("区块已更新"); } });
  const deleteMut = useMutation({ mutationFn: deleteBlock, onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["blocks"] }); toast.success("区块已删除"); } });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">页面布局</h1>
        <Button onClick={() => { setEditingBlock(null); setEditorOpen(true); }}>
          <Plus className="w-4 h-4 mr-2" />添加区块
        </Button>
      </div>

      <Tabs value={activePage} onValueChange={setActivePage}>
        <TabsList>
          {pages.map(p => (
            <TabsTrigger key={p.route} value={p.route}>{p.label}</TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {isLoading ? (
        <p className="text-muted-foreground text-sm">加载中...</p>
      ) : pageBlocks.length === 0 ? (
        <p className="text-muted-foreground text-sm py-12 text-center">暂无区块，点击上方按钮添加</p>
      ) : (
        <div className="space-y-3">
          {pageBlocks.map((block: Block) => (
            <Card key={block.id} className={!block.enabled ? "opacity-50" : ""}>
              <CardContent className="flex items-center gap-4 p-4">
                <GripVertical className="w-5 h-5 text-muted-foreground cursor-grab" />
                <div className="flex-1 min-w-0">
                  <div className="font-medium">{block.title}</div>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    {block.source_type} · {block.display_count}条 · 按{block.sort_by === "score" ? "热度" : "时间"}排序
                  </div>
                </div>
                <Switch checked={block.enabled} onCheckedChange={v => updateMut.mutate({ id: block.id, data: { enabled: v } })} />
                <Button variant="ghost" size="icon" onClick={() => { setEditingBlock(block); setEditorOpen(true); }}>
                  <Pencil className="w-4 h-4" />
                </Button>
                <Button variant="ghost" size="icon" onClick={() => { if (confirm("确定删除？")) deleteMut.mutate(block.id); }}>
                  <Trash2 className="w-4 h-4 text-destructive" />
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <BlockEditor
        open={editorOpen}
        block={editingBlock}
        onClose={() => { setEditorOpen(false); setEditingBlock(null); }}
        onSave={(data) => {
          if (editingBlock) {
            updateMut.mutate({ id: editingBlock.id, data });
          } else {
            createMut.mutate(data as any);
          }
        }}
      />
    </div>
  );
}
```

- [ ] **Step 3: 添加路由**

在 `App.tsx` 中添加：

```tsx
import { AdminLayoutPage } from "./pages/AdminLayoutPage";
// ...
<Route path="/admin/layout" element={<AdminLayoutPage />} />
```

- [ ] **Step 4: 运行构建验证**

```bash
cd frontend && npm run build
```

- [ ] **Step 5: 提交**

```bash
git add frontend
git commit -m "feat: add admin layout management page"
```

---

### Task 6: 公开页面动态渲染

**Files:**
- Modify: `frontend/src/pages/SummaryPage.tsx`
- Modify: `frontend/src/pages/StockTopicPage.tsx`
- Create: `frontend/src/hooks/use-page-blocks.ts`
- Create: `frontend/src/components/layout/BlockCard.tsx`

- [ ] **Step 1: 创建 usePageBlocks hook**

创建 `frontend/src/hooks/use-page-blocks.ts`：

```ts
import { useQuery } from "@tanstack/react-query";
import { fetchPageBlocks } from "@/api/client";
import type { PageBlocksResponse } from "@/api/types";

export function usePageBlocks(route: string) {
  return useQuery<PageBlocksResponse>({
    queryKey: ["page-blocks", route],
    queryFn: () => fetchPageBlocks(route),
  });
}
```

- [ ] **Step 2: 创建 BlockCard 组件**

创建 `frontend/src/components/layout/BlockCard.tsx`：

```tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";  // 手动创建或复用 shadcn
import { Pin, TrendingUp } from "lucide-react";
import { cn } from "@/lib/utils";

interface BlockCardProps {
  title: string;
  summary: string;
  tags?: string[];
  score?: number;
  isPinned?: boolean;
  symbols?: string[];
  className?: string;
}

export function BlockCard({ title, summary, tags, score, isPinned, symbols, className }: BlockCardProps) {
  return (
    <div className={cn("p-4 border rounded-lg bg-card hover:shadow-sm transition-shadow", isPinned && "border-l-2 border-l-orange-500", className)}>
      <div className="flex items-start justify-between gap-2 mb-2">
        <h3 className="font-semibold text-sm leading-snug">
          {isPinned && <Pin className="w-3 h-3 inline text-orange-500 mr-1" />}
          {title}
        </h3>
        {score != null && (
          <span className="text-xs text-muted-foreground flex items-center gap-1 shrink-0">
            <TrendingUp className="w-3 h-3" />{score}
          </span>
        )}
      </div>
      <p className="text-sm text-muted-foreground line-clamp-3 mb-3">{summary}</p>
      <div className="flex items-center gap-2 flex-wrap">
        {symbols?.map(s => (
          <span key={s} className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded font-medium">{s}</span>
        ))}
        {tags?.map(t => (
          <span key={t} className="text-xs bg-muted text-muted-foreground px-2 py-0.5 rounded">{t}</span>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: 改造 SummaryPage 为 PageRenderer**

重写 `frontend/src/pages/SummaryPage.tsx`：

```tsx
import { usePageBlocks } from "@/hooks/use-page-blocks";
import { BlockCard } from "@/components/layout/BlockCard";
import { Separator } from "@/components/ui/separator";

export function SummaryPage() {
  const { data, isLoading, error } = usePageBlocks("/");

  if (isLoading) return <div className="text-center py-12 text-muted-foreground">加载中...</div>;
  if (error) return <div className="text-center py-12 text-red-500">加载失败</div>;

  const blocks = data?.blocks ?? [];

  return (
    <div className="space-y-8">
      {blocks.map((block) => (
        <section key={block.id}>
          <h2 className="text-lg font-bold mb-4">{block.title}</h2>
          <div className="space-y-3">
            {block.data?.length === 0 && <p className="text-sm text-muted-foreground">暂无数据</p>}
            {block.data?.map((item: any, i: number) => (
              <BlockCard
                key={item.id ?? i}
                title={item.title ?? item.name ?? ""}
                summary={item.summary ?? item.content ?? ""}
                tags={item.tags_json ?? item.tags}
                score={item.score ?? item.value}
                isPinned={item.is_pinned}
                symbols={item.related_symbols_json ?? (item.code ? [item.code] : undefined)}
              />
            ))}
          </div>
          <Separator className="mt-6" />
        </section>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: 改造 StockTopicPage**

同样改为 PageRenderer，route 参数传 `/topics/stocks`。

```tsx
import { usePageBlocks } from "@/hooks/use-page-blocks";
import { BlockCard } from "@/components/layout/BlockCard";
import { Separator } from "@/components/ui/separator";

export function StockTopicPage() {
  const { data, isLoading, error } = usePageBlocks("/topics/stocks");
  // ... 同 SummaryPage，代码结构完全一致
}
```

- [ ] **Step 5: 运行构建验证**

```bash
cd frontend && npm run build
```

- [ ] **Step 6: 提交**

```bash
git add frontend
git commit -m "feat: dynamic page rendering with block cards"
```

---

### Task 7: 端到端验证和文档更新

- [ ] **Step 1: 运行后端全部测试**

```bash
cd backend && APP_SECRET_KEY=test-key /Users/lws/opt/anaconda3/envs/daily_highlights/bin/pytest tests/ -v
```

预期：全部通过（含新增的 test_page_blocks.py + test_blocks_api.py）

- [ ] **Step 2: 运行前端全部测试**

```bash
cd frontend && npm test
```

预期：全部通过

- [ ] **Step 3: 运行前端构建**

```bash
cd frontend && npm run build
```

预期：成功

- [ ] **Step 4: 启动后端验证**

```bash
cd backend && /Users/lws/opt/anaconda3/envs/daily_highlights/bin/uvicorn app.main:app --reload
```

验证：
- `curl http://localhost:8000/api/admin/blocks` → `[]`
- `curl -X POST http://localhost:8000/api/admin/blocks -H "Content-Type: application/json" -d '{"page_route":"/","title":"测试","source_type":"topic","source_config":{"topic_id":1}}'` → 返回创建的区块
- `curl http://localhost:8000/api/public/pages/%2F/blocks` → 返回区块数据

- [ ] **Step 5: 提交**

```bash
git commit -m "chore: final verification and docs"
```

---

## 自检清单

- 范围控制：
  - `topic` source_type 数据聚合已实现
  - `hot_stocks` / `hot_events` / `search` / `screener` 的雪球 API 代理留到后续
  - 拖拽排序 UI 已有（GripVertical 图标），实际 DnD 逻辑（@dnd-kit）留到后续
  - 页面 CRUD 不在此范围（固定摘要页 + 股票页）
- 测试：后端 CRUD API 完整测试覆盖
- 前端：所有管理页面改 Tailwind + shadcn/ui，公开页改 PageRenderer
