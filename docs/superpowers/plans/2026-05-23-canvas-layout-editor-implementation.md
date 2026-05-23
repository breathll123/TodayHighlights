# 画布布局编辑器 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将页面布局管理从表单列表升级为可视化画布编辑器——拖拽定位、缩放方块、草稿发布、移动端适配。

**Architecture:** 后端 `page_blocks` 表增加 grid 布局字段 + 发布 API；前端用 `react-grid-layout` 实现画布拖拽编辑器，`/admin/layout` 重写为可视化编辑模式；前台用 CSS Grid 渲染。

**Tech Stack:** Python FastAPI + SQLAlchemy + Alembic；React + react-grid-layout + Tailwind CSS + shadcn/ui

---

## 文件结构

```
backend/
  migrations/versions/20260523_0003_page_blocks_grid.py  ← 新建迁移
  app/
    models/entities.py       ← PageBlock 增加 grid 字段
    schemas/admin.py         ← BlockCreate/BlockUpdate 增加 grid 字段
    api/admin.py             ← 增加 publish 端点
    api/public.py            ← 修改 blocks 查询过滤 status=published
    services/blocks.py       ← get_page_blocks 增加 status 过滤 + grid 排序

frontend/
  src/
    api/
      client.ts              ← 增加 publishPage API
      types.ts               ← Block 类型增加 grid 字段
    components/admin/
      CanvasEditor.tsx        ← 新建：画布编辑器（react-grid-layout 容器）
      CanvasBlock.tsx         ← 新建：画布上的单个方块（带拖拽手柄+缩放）
      BlockConfigPanel.tsx    ← 新建：右侧配置面板
      SizePresetPicker.tsx    ← 新建：添加方块时的预设尺寸选择器
    pages/
      AdminLayoutPage.tsx     ← 重写：画布编辑视图 + 工具栏
    hooks/
      use-canvas-layout.ts    ← 新建：画布状态管理
    lib/
      grid-utils.ts           ← 新建：碰撞检测、边界检查
```

---

### Task 1: 数据模型迁移

**Files:**
- Create: `backend/migrations/versions/20260523_0003_page_blocks_grid.py`
- Modify: `backend/app/models/entities.py`
- Modify: `backend/app/schemas/admin.py`

- [ ] **Step 1: 创建迁移文件**

创建 `backend/migrations/versions/20260523_0003_page_blocks_grid.py`：

```python
"""page_blocks grid layout

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-23
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("page_blocks", sa.Column("block_key", sa.String(36), nullable=False, server_default=""))
    op.add_column("page_blocks", sa.Column("col_span", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("page_blocks", sa.Column("row_span", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("page_blocks", sa.Column("grid_x", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("page_blocks", sa.Column("grid_y", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("page_blocks", sa.Column("status", sa.String(20), nullable=False, server_default="draft"))


def downgrade() -> None:
    op.drop_column("page_blocks", "status")
    op.drop_column("page_blocks", "grid_y")
    op.drop_column("page_blocks", "grid_x")
    op.drop_column("page_blocks", "row_span")
    op.drop_column("page_blocks", "col_span")
    op.drop_column("page_blocks", "block_key")
```

- [ ] **Step 2: 更新 PageBlock 模型**

在 `backend/app/models/entities.py` 的 `PageBlock` 类中，在 `enabled` 字段后面添加：

```python
    block_key: Mapped[str] = mapped_column(String(36), default="", nullable=False)
    col_span: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    row_span: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    grid_x: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    grid_y: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
```

- [ ] **Step 3: 更新 Schema**

在 `backend/app/schemas/admin.py` 的 `BlockCreate` 中添加：

```python
    block_key: str = ""
    col_span: int = 1
    row_span: int = 1
    grid_x: int = 0
    grid_y: int = 0
```

在 `BlockUpdate` 中添加同样的可选字段（均为 `int | None = None`），以及 `status: str | None = None`。

在 `BlockRead` 中添加 `block_key`、`col_span`、`row_span`、`grid_x`、`grid_y`、`status` 字段。

- [ ] **Step 4: 更新模型测试**

在 `backend/tests/test_page_blocks.py` 中添加新字段的测试断言：

```python
def test_page_block_grid_fields() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        block = PageBlock(
            page_route="/", title="测试", source_type="topic",
            source_config={}, block_key="abc-123",
            col_span=2, row_span=1, grid_x=0, grid_y=0, status="draft",
        )
        session.add(block)
        session.commit()
        saved = session.query(PageBlock).one()
        assert saved.block_key == "abc-123"
        assert saved.col_span == 2
        assert saved.status == "draft"
```

- [ ] **Step 5: 运行迁移和测试**

```bash
cd backend
# 用 Python 创建表（绕过 Alembic ConfigParser 问题）
/Users/lws/opt/anaconda3/envs/daily_highlights/bin/python -c "
from app.core.database import engine, Base
from app.models.entities import PageBlock
Base.metadata.create_all(engine)
print('Migration done')
"
APP_SECRET_KEY=test-key /Users/lws/opt/anaconda3/envs/daily_highlights/bin/pytest tests/test_page_blocks.py -v
```

预期：`2 passed`

- [ ] **Step 6: 提交**

```bash
git add backend
git commit -m "feat: add grid layout fields to page_blocks"
```

---

### Task 2: 发布 API + 公开 API 更新

**Files:**
- Modify: `backend/app/api/admin.py` — 添加 publish 端点
- Modify: `backend/app/api/public.py` — 修改 blocks 查询过滤 status=published
- Modify: `backend/app/services/blocks.py` — 增加 status 过滤 + grid 排序
- Create: `backend/tests/test_publish.py`

- [ ] **Step 1: 编写发布 API 测试**

创建 `backend/tests/test_publish.py`：

```python
from fastapi.testclient import TestClient


def test_publish_page(client: TestClient) -> None:
    # 创建 draft 方块
    client.post("/api/admin/blocks", json={
        "page_route": "/", "title": "方块1", "source_type": "topic",
        "source_config": {"topic_id": 1}, "block_key": "key-1",
        "col_span": 2, "status": "draft",
    })
    client.post("/api/admin/blocks", json={
        "page_route": "/", "title": "方块2", "source_type": "hot_stocks",
        "source_config": {"type": 10}, "block_key": "key-2",
        "col_span": 1, "status": "draft",
    })

    # 发布
    resp = client.post("/api/admin/pages/%2F/publish")
    assert resp.status_code == 200
    assert resp.json() == {"published": True, "blocks": 2}

    # 前台应该返回 2 个 published 方块
    resp2 = client.get("/api/public/pages/%2F/blocks")
    assert len(resp2.json()["blocks"]) == 2


def test_publish_removes_deleted_blocks(client: TestClient) -> None:
    # 先创建并发布
    client.post("/api/admin/blocks", json={
        "page_route": "/", "title": "旧方块", "source_type": "topic",
        "source_config": {"topic_id": 1}, "block_key": "old-key", "status": "draft",
    })
    client.post("/api/admin/pages/%2F/publish")
    assert len(client.get("/api/public/pages/%2F/blocks").json()["blocks"]) == 1

    # 删除 draft，再发布
    blocks = client.get("/api/admin/blocks").json()
    client.delete(f"/api/admin/blocks/{blocks[0]['id']}")

    client.post("/api/admin/pages/%2F/publish")
    assert len(client.get("/api/public/pages/%2F/blocks").json()["blocks"]) == 0
```

- [ ] **Step 2: 实现发布端点**

在 `backend/app/api/admin.py` 的 `auth_router`（不受保护的登录路由）中添加 publish 端点。但 publish 应该在 admin router（受保护）中。添加到 `router` 末尾：

```python
@router.post("/pages/{route:path}/publish")
def publish_page(route: str, session: Session = Depends(get_session)) -> dict:
    route = "/" + route if not route.startswith("/") else route

    # 删除旧的 published
    session.execute(
        delete(PageBlock).where(
            PageBlock.page_route == route,
            PageBlock.status == "published"
        )
    )

    # 复制 draft → published
    drafts = session.scalars(
        select(PageBlock).where(
            PageBlock.page_route == route,
            PageBlock.status == "draft"
        )
    ).all()

    count = 0
    for d in drafts:
        published = PageBlock(
            block_key=d.block_key,
            page_route=d.page_route,
            title=d.title,
            source_type=d.source_type,
            source_config=d.source_config,
            display_style=d.display_style,
            display_count=d.display_count,
            sort_by=d.sort_by,
            col_span=d.col_span,
            row_span=d.row_span,
            grid_x=d.grid_x,
            grid_y=d.grid_y,
            status="published",
            enabled=True,
        )
        session.add(published)
        count += 1

    session.commit()
    return {"published": True, "blocks": count}
```

需要添加 `from sqlalchemy import delete` 到文件顶部。

- [ ] **Step 3: 更新公开 API 和 blocks 服务**

在 `backend/app/services/blocks.py` 的 `get_page_blocks` 中，添加 `status="published"` 过滤和 grid 排序：

```python
def get_page_blocks(session: Session, route: str) -> list[dict]:
    stmt = (
        select(PageBlock)
        .where(
            PageBlock.page_route == route,
            PageBlock.enabled.is_(True),
            PageBlock.status == "published",
        )
        .order_by(PageBlock.grid_y, PageBlock.grid_x, PageBlock.sort_order)
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
            "col_span": block.col_span,
            "row_span": block.row_span,
            "grid_x": block.grid_x,
            "grid_y": block.grid_y,
            "data": resolve_block_data(session, block),
        }
        result.append(item)
    return result
```

- [ ] **Step 4: 运行测试**

```bash
cd backend
APP_SECRET_KEY=test-key /Users/lws/opt/anaconda3/envs/daily_highlights/bin/pytest tests/test_publish.py tests/test_blocks_api.py -v
```

预期：所有测试通过。

- [ ] **Step 5: 更新现有测试以包含 status=published**

现有的 `test_blocks_api.py` 创建方块时没有传 `status`，默认是 `draft`。但公开 API 现在只返回 `status=published`。需要在创建方块时传 `"status": "published"`。

更新每个创建方块的 `client.post("/api/admin/blocks", json={...})` 调用，在 JSON 中添加 `"status": "published"`。

- [ ] **Step 6: 运行全部测试**

```bash
APP_SECRET_KEY=test-key /Users/lws/opt/anaconda3/envs/daily_highlights/bin/pytest tests/ -v
```

预期：全部通过。

- [ ] **Step 7: 提交**

```bash
git add backend
git commit -m "feat: add publish API and published status filtering"
```

---

### Task 3: 前端类型和 API 更新

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: 更新 Block 类型**

在 `frontend/src/api/types.ts` 的 `Block` 接口中添加：

```ts
export interface Block {
  // ... existing fields
  block_key: string;
  col_span: number;
  row_span: number;
  grid_x: number;
  grid_y: number;
  status: "draft" | "published";
}
```

- [ ] **Step 2: 添加 publishPage API**

在 `frontend/src/api/client.ts` 中添加：

```ts
export function publishPage(route: string): Promise<{ published: boolean; blocks: number }> {
  return api.post(`/api/admin/pages/${route}/publish`).then((r) => r.data);
}
```

- [ ] **Step 3: 验证构建**

```bash
cd frontend && npm run build
```

预期：成功。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/api
git commit -m "feat: add grid fields to Block type and publishPage API"
```

---

### Task 4: 画布编辑器核心组件

**Files:**
- Create: `frontend/src/lib/grid-utils.ts`
- Create: `frontend/src/hooks/use-canvas-layout.ts`
- Create: `frontend/src/components/admin/CanvasBlock.tsx`
- Create: `frontend/src/components/admin/SizePresetPicker.tsx`
- Create: `frontend/src/components/admin/BlockConfigPanel.tsx`
- Create: `frontend/src/components/admin/CanvasEditor.tsx`
- Install: `react-grid-layout` + types

- [ ] **Step 1: 安装依赖**

```bash
cd frontend
npm install react-grid-layout
npm install -D @types/react-grid-layout
```

- [ ] **Step 2: 创建 grid-utils**

创建 `frontend/src/lib/grid-utils.ts`：

```ts
import type { Block } from "@/api/types";

/** Check if two blocks overlap on the grid */
export function hasCollision(a: { grid_x: number; grid_y: number; col_span: number; row_span: number }, b: { grid_x: number; grid_y: number; col_span: number; row_span: number }): boolean {
  return (
    a.grid_x < b.grid_x + b.col_span &&
    a.grid_x + a.col_span > b.grid_x &&
    a.grid_y < b.grid_y + b.row_span &&
    a.grid_y + a.row_span > b.grid_y
  );
}

/** Find first available grid position for a new block */
export function findAvailablePosition(blocks: Block[], colSpan: number, rowSpan: number): { x: number; y: number } {
  for (let y = 0; y < 20; y++) {
    for (let x = 0; x <= 4 - colSpan; x++) {
      const candidate = { grid_x: x, grid_y: y, col_span: colSpan, row_span: rowSpan };
      const blocked = blocks.some((b) => hasCollision(candidate, b));
      if (!blocked) return { x, y };
    }
  }
  return { x: 0, y: blocks.length };
}

/** Clamp col_span to [1, 4], row_span to [1, 6] */
export function clampSize(colSpan: number, rowSpan: number): { col: number; row: number } {
  return {
    col: Math.max(1, Math.min(4, colSpan)),
    row: Math.max(1, Math.min(6, rowSpan)),
  };
}

export const SIZE_PRESETS = [
  { label: "小卡片", icon: "□", col: 1, row: 1 },
  { label: "中方块", icon: "□□", col: 2, row: 1 },
  { label: "大卡片", icon: "□□ / □□", col: 2, row: 2 },
  { label: "宽横幅", icon: "□□□□", col: 4, row: 1 },
  { label: "全宽", icon: "□□□□ / □□□□", col: 4, row: 2 },
] as const;
```

- [ ] **Step 3: 创建 CanvasBlock**

创建 `frontend/src/components/admin/CanvasBlock.tsx`：

```tsx
import { GripHorizontal, Pencil, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { Block } from "@/api/types";

interface Props {
  block: Block;
  onEdit: () => void;
  onDelete: () => void;
}

export function CanvasBlock({ block, onEdit, onDelete }: Props) {
  return (
    <div className="h-full bg-card border rounded-xl shadow-sm overflow-hidden flex flex-col">
      <div className="flex items-center justify-between px-3 py-2 bg-muted/30 border-b drag-handle cursor-grab active:cursor-grabbing">
        <div className="flex items-center gap-2 min-w-0">
          <GripHorizontal className="w-4 h-4 text-muted-foreground shrink-0" />
          <span className="text-xs font-medium truncate">{block.title}</span>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <Badge variant="secondary" className="text-[10px] px-1.5">{block.source_type}</Badge>
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={(e) => { e.stopPropagation(); onEdit(); }}>
            <Pencil className="w-3 h-3" />
          </Button>
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={(e) => { e.stopPropagation(); onDelete(); }}>
            <Trash2 className="w-3 h-3 text-destructive" />
          </Button>
        </div>
      </div>
      <div className="flex-1 p-3 text-xs text-muted-foreground flex items-center justify-center">
        {block.display_count}条 · {block.display_style === "list" ? "列表" : "卡片"}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: 创建 SizePresetPicker**

创建 `frontend/src/components/admin/SizePresetPicker.tsx`：

```tsx
import { SIZE_PRESETS } from "@/lib/grid-utils";

interface Props {
  onSelect: (col: number, row: number) => void;
}

export function SizePresetPicker({ onSelect }: Props) {
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium">选择尺寸</p>
      <div className="grid grid-cols-2 gap-2">
        {SIZE_PRESETS.map((p) => (
          <button
            key={p.label}
            className="border rounded-lg p-3 text-left hover:bg-muted transition-colors"
            onClick={() => onSelect(p.col, p.row)}
          >
            <div className="text-xs text-muted-foreground mb-1">{p.icon}</div>
            <div className="text-sm font-medium">{p.label}</div>
            <div className="text-[10px] text-muted-foreground">{p.col}×{p.row}</div>
          </button>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: 创建 BlockConfigPanel**

创建 `frontend/src/components/admin/BlockConfigPanel.tsx`（基于现有 BlockEditor 的配置表单，去掉 Dialog 包装，改为侧面板）：

```tsx
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import { SIZE_PRESETS } from "@/lib/grid-utils";
import type { Block } from "@/api/types";

interface Props {
  form: Omit<Block, "id" | "created_at" | "updated_at">;
  onChange: (f: Omit<Block, "id" | "created_at" | "updated_at">) => void;
  onSave: () => void;
  onCancel: () => void;
}

export function BlockConfigPanel({ form, onChange, onSave, onCancel }: Props) {
  return (
    <div className="w-80 border-l bg-card h-full overflow-y-auto p-4 space-y-4">
      <h3 className="font-semibold text-sm">方块配置</h3>

      <div className="space-y-2">
        <Label>标题</Label>
        <Input value={form.title} onChange={(e) => onChange({ ...form, title: e.target.value })} />
      </div>

      <div className="space-y-2">
        <Label>数据来源</Label>
        <Select value={form.source_type} onValueChange={(v) => onChange({ ...form, source_type: v as Block["source_type"] })}>
          <SelectTrigger><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="topic">本地看点</SelectItem>
            <SelectItem value="hot_stocks">热股榜</SelectItem>
            <SelectItem value="hot_events">热门话题</SelectItem>
            <SelectItem value="screener">活跃股票</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Source-specific config fields — same as current BlockEditor */}

      <div className="space-y-2">
        <Label>展示条数 ({form.display_count})</Label>
        <Slider value={[form.display_count]} onValueChange={([v]) => onChange({ ...form, display_count: v })} min={1} max={20} step={1} />
      </div>

      <div className="space-y-2">
        <Label>展示形式</Label>
        <Select value={form.display_style} onValueChange={(v) => onChange({ ...form, display_style: v as "card" | "list" })}>
          <SelectTrigger><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="card">卡片</SelectItem>
            <SelectItem value="list">列表</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label>预设尺寸</Label>
        <div className="grid grid-cols-3 gap-1.5">
          {SIZE_PRESETS.map((p) => (
            <button
              key={p.label}
              className={`border rounded px-2 py-1 text-xs ${form.col_span === p.col && form.row_span === p.row ? "bg-primary text-primary-foreground" : "hover:bg-muted"}`}
              onClick={() => onChange({ ...form, col_span: p.col, row_span: p.row })}
            >
              {p.col}×{p.row}
            </button>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-2">
        <Switch checked={form.enabled} onCheckedChange={(v) => onChange({ ...form, enabled: v })} />
        <Label>启用</Label>
      </div>

      <div className="flex gap-2 pt-2">
        <Button size="sm" className="flex-1" onClick={onSave}>保存</Button>
        <Button size="sm" variant="outline" className="flex-1" onClick={onCancel}>取消</Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 6: 创建 CanvasEditor 容器**

创建 `frontend/src/components/admin/CanvasEditor.tsx`（使用 react-grid-layout）：

```tsx
import { useCallback } from "react";
import GridLayout from "react-grid-layout";
import "react-grid-layout/css/styles.css";
import { CanvasBlock } from "./CanvasBlock";
import { hasCollision, clampSize } from "@/lib/grid-utils";
import type { Block } from "@/api/types";
import { toast } from "sonner";

interface Props {
  blocks: Block[];
  onLayoutChange: (blocks: Block[]) => void;
  onEdit: (block: Block) => void;
  onDelete: (id: number) => void;
}

export function CanvasEditor({ blocks, onLayoutChange, onEdit, onDelete }: Props) {
  const layout = blocks.map((b) => ({
    i: String(b.id),
    x: b.grid_x,
    y: b.grid_y,
    w: b.col_span,
    h: b.row_span,
  }));

  const handleDragStop: GridLayout.ItemCallback = useCallback(
    (items, oldItem, newItem) => {
      const moved = blocks.find((b) => String(b.id) === newItem.i);
      if (!moved) return;

      const candidate = {
        ...moved,
        grid_x: newItem.x,
        grid_y: newItem.y,
        col_span: newItem.w,
        row_span: newItem.h,
      };

      const others = blocks.filter((b) => String(b.id) !== newItem.i);
      const collision = others.some((b) => hasCollision(candidate, b));
      if (collision) {
        toast.error("该位置已有其他组件");
        return; // react-grid-layout will revert
      }

      const updated = blocks.map((b) =>
        String(b.id) === newItem.i ? candidate : b
      );
      onLayoutChange(updated);
    },
    [blocks, onLayoutChange]
  );

  const handleResizeStop: GridLayout.ItemCallback = useCallback(
    (items, oldItem, newItem) => {
      const { col, row } = clampSize(newItem.w, newItem.h);
      const block = blocks.find((b) => String(b.id) === newItem.i);
      if (!block) return;

      if (newItem.x + col > 4) {
        toast.error("方块不能超出画布边界");
        return;
      }

      const updated = blocks.map((b) =>
        String(b.id) === newItem.i
          ? { ...b, grid_x: newItem.x, grid_y: newItem.y, col_span: col, row_span: row }
          : b
      );
      onLayoutChange(updated);
    },
    [blocks, onLayoutChange]
  );

  return (
    <GridLayout
      className="layout"
      layout={layout}
      cols={4}
      rowHeight={160}
      width={800}
      margin={[12, 12]}
      draggableHandle=".drag-handle"
      isResizable
      onDragStop={handleDragStop}
      onResizeStop={handleResizeStop}
      compactType={null}
      preventCollision={false}
    >
      {blocks.map((b) => (
        <div key={String(b.id)}>
          <CanvasBlock block={b} onEdit={() => onEdit(b)} onDelete={() => onDelete(b.id)} />
        </div>
      ))}
    </GridLayout>
  );
}
```

- [ ] **Step 7: 验证构建**

```bash
cd frontend && npm run build
```

预期：成功。

- [ ] **Step 8: 提交**

```bash
git add frontend
git commit -m "feat: add canvas editor core components"
```

---

### Task 5: 重写 AdminLayoutPage 为画布视图

**Files:**
- Modify: `frontend/src/pages/AdminLayoutPage.tsx`

- [ ] **Step 1: 重写 AdminLayoutPage**

重写为画布编辑模式——页面选择 Tab、画布区、右侧配置面板、工具栏（编辑/预览/发布）。

完整的 `AdminLayoutPage.tsx` 代码（略去，太长，实际写的时候包含完整代码）。

核心结构：

```tsx
export function AdminLayoutPage() {
  const [activePage, setActivePage] = useState("/");
  const [mode, setMode] = useState<"edit" | "preview">("edit");
  const [configPanel, setConfigPanel] = useState<{ open: boolean; block: Block | null }>({ open: false, block: null });
  // ... React Query hooks for blocks CRUD

  const handleAddBlock = (col: number, row: number) => {
    const pos = findAvailablePosition(pageBlocks, col, row);
    createMut.mutate({
      page_route: activePage, title: "新方块", source_type: "topic",
      source_config: { topic_id: 1 }, block_key: crypto.randomUUID(),
      col_span: col, row_span: row, grid_x: pos.x, grid_y: pos.y,
      display_style: "card", display_count: 5, sort_by: "created_at",
      enabled: true, status: "draft",
    });
  };

  const handlePublish = () => {
    publishPage(activeRoute).then(() => toast.success("已发布"));
  };

  return (
    <div className="flex h-[calc(100vh-3.5rem)]">
      {/* 画布区 */}
      <div className="flex-1 overflow-auto p-6">
        <div className="flex items-center justify-between mb-4">
          <Tabs value={activePage} onValueChange={setActivePage}>...</Tabs>
          <div className="flex items-center gap-2">
            <Button variant={mode === "edit" ? "default" : "outline"} onClick={() => setMode("edit")}>编辑</Button>
            <Button variant={mode === "preview" ? "default" : "outline"} onClick={() => setMode("preview")}>预览</Button>
            <Button onClick={handlePublish}>发布</Button>
          </div>
        </div>

        {mode === "edit" ? (
          <>
            <CanvasEditor blocks={pageBlocks} onLayoutChange={...} onEdit={...} onDelete={...} />
            <Button className="mt-4" onClick={() => setSizePickerOpen(true)}>+ 添加方块</Button>
            <SizePresetPicker open={sizePickerOpen} onSelect={handleAddBlock} onClose={...} />
          </>
        ) : (
          <PreviewGrid blocks={pageBlocks} />
        )}
      </div>

      {/* 配置面板 */}
      {configPanel.open && (
        <BlockConfigPanel form={...} onChange={...} onSave={...} onCancel={...} />
      )}
    </div>
  );
}
```

- [ ] **Step 2: 验证构建 + 测试**

```bash
cd frontend && npm run build && npm test
```

预期：构建成功，测试通过。

- [ ] **Step 3: 提交**

```bash
git add frontend
git commit -m "feat: rewrite admin layout page as canvas editor"
```

---

### Task 6: 前台 CSS Grid 渲染 + 移动端适配

**Files:**
- Modify: `frontend/src/pages/SummaryPage.tsx`
- Modify: `frontend/src/pages/StockTopicPage.tsx`
- Create: `frontend/src/components/layout/GridRenderer.tsx`
- Create: `frontend/src/components/layout/BlockSkeleton.tsx`

- [ ] **Step 1: 创建 GridRenderer 组件**

创建 `frontend/src/components/layout/GridRenderer.tsx`：

```tsx
import { BlockCard } from "./BlockCard";
import { BlockListItem } from "./BlockListItem";
import { BlockSkeleton } from "./BlockSkeleton";

export function GridRenderer({ blocks, isLoading }: { blocks: any[]; isLoading: boolean }) {
  if (isLoading) {
    return (
      <div className="page-grid">
        {[1, 2, 3, 4].map((i) => (
          <BlockSkeleton key={i} colSpan={1} rowSpan={1} />
        ))}
      </div>
    );
  }

  return (
    <div className="page-grid">
      {blocks.map((block) => (
        <section key={block.id} className="space-y-3" style={{ gridColumn: `span ${block.col_span || 1}`, gridRow: `span ${block.row_span || 1}` }}>
          <h2 className="text-sm font-bold text-muted-foreground">{block.title}</h2>
          <div className={block.display_style === "list" ? "border rounded-lg bg-card" : "space-y-2"}>
            {block.data?.map((item: any, i: number) => {
              const props = {
                key: item.id ?? i,
                title: item.title ?? item.name ?? "",
                summary: item.summary ?? item.content ?? "",
                tags: item.tags_json ?? item.tags,
                score: item.score ?? item.value,
                isPinned: item.is_pinned,
                symbols: item.related_symbols_json ?? item.symbols ?? (item.code ? [item.code] : undefined),
                url: item.url,
              };
              return block.display_style === "list" ? <BlockListItem {...props} /> : <BlockCard {...props} />;
            })}
          </div>
        </section>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: 创建 BlockSkeleton**

创建 `frontend/src/components/layout/BlockSkeleton.tsx`：

```tsx
export function BlockSkeleton({ colSpan, rowSpan }: { colSpan: number; rowSpan: number }) {
  return (
    <div className="animate-pulse bg-card rounded-xl border p-5" style={{ gridColumn: `span ${colSpan}`, gridRow: `span ${rowSpan}` }}>
      <div className="h-4 bg-muted rounded w-2/3 mb-3" />
      <div className="h-3 bg-muted rounded w-full mb-2" />
      <div className="h-3 bg-muted rounded w-4/5 mb-2" />
      <div className="h-3 bg-muted rounded w-1/2" />
    </div>
  );
}
```

- [ ] **Step 3: 更新 SummaryPage 和 StockTopicPage**

两个页面都改用 `GridRenderer`：

```tsx
export function SummaryPage() {
  const { data, isLoading, error } = usePageBlocks("/");
  if (error) return <div className="text-center py-12 text-destructive">加载失败</div>;
  const blocks = data?.blocks ?? [];
  if (!isLoading && blocks.length === 0) {
    return <div className="text-center py-12 text-muted-foreground">暂无内容</div>;
  }
  return <GridRenderer blocks={blocks} isLoading={isLoading} />;
}
```

- [ ] **Step 4: 添加移动端 CSS**

在 `frontend/src/styles/globals.css` 末尾添加：

```css
.page-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

@media (max-width: 768px) {
  .page-grid {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .page-grid > * {
    width: 100% !important;
    grid-column: span 1 !important;
  }
}
```

- [ ] **Step 5: 验证构建 + 测试**

```bash
cd frontend && npm run build && npm test
```

- [ ] **Step 6: 提交**

```bash
git add frontend
git commit -m "feat: add CSS grid rendering, skeleton loading, mobile responsive"
```

---

### Task 7: 端到端验证

- [ ] **Step 1: 运行后端全部测试**

```bash
cd backend
APP_SECRET_KEY=test-key /Users/lws/opt/anaconda3/envs/daily_highlights/bin/pytest tests/ -v
```

预期：全部通过。

- [ ] **Step 2: 运行前端全部测试 + 构建**

```bash
cd frontend && npm test && npm run build
```

预期：测试通过，构建成功。

- [ ] **Step 3: 现有 draft 数据迁移**

将现有 `page_blocks` 中所有非 NULL 的 `status` 列更新为 `draft`。如果还没有数据，跳过。

```sql
UPDATE page_blocks SET status = 'draft' WHERE status = '';
```

- [ ] **Step 4: 冒烟测试**

启动后端 + 前端：
1. 访问 `/admin/layout` → 画布编辑器
2. 添加几个不同尺寸的方块
3. 拖拽方块到不同位置
4. 点击发布
5. 访问前台 `/` → 看到 CSS Grid 布局
6. 手机宽度 → 单列流式布局
7. 骨骼屏动画显示

- [ ] **Step 5: 提交**

```bash
git commit -m "chore: final verification and data migration"
```

---

## 自检清单

- 范围控制：
  - 拖拽碰撞检测已实现（回弹 + Toast）
  - 尺寸边界硬编码（col 1-4, row 1-6）
  - 移动端 768px 断点降级
  - 骨架屏在 GridRenderer 中加载态显示
  - 发布为事务式覆盖写入
  - block_key 由前端 `crypto.randomUUID()` 生成
  - 预设尺寸选择器 5 种默认
  - 未实现：无数据源配额的拖拽限制、撤销/重做
- 测试：后端 publish 端点测试 + blocks grid 字段测试
