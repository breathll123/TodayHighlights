# 画布布局编辑器 设计

> 将页面布局管理从表单列表升级为可视化画布编辑器，支持拖拽定位、缩放、草稿发布、移动端适配。

---

## 1. 数据模型

### `page_blocks` 表变更

```sql
ALTER TABLE page_blocks
  ADD COLUMN block_key  VARCHAR(36)  NOT NULL DEFAULT '' COMMENT 'UUID 稳定标识',
  ADD COLUMN col_span   INTEGER      NOT NULL DEFAULT 1,
  ADD COLUMN row_span   INTEGER      NOT NULL DEFAULT 1,
  ADD COLUMN grid_x     INTEGER      NOT NULL DEFAULT 0,
  ADD COLUMN grid_y     INTEGER      NOT NULL DEFAULT 0,
  ADD COLUMN status     VARCHAR(20)  NOT NULL DEFAULT 'draft' COMMENT 'draft | published';
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `block_key` | UUID string | 跨 draft/published 的稳定标识，React key 绑定 |
| `col_span` | int 1-4 | 列跨度，4 列网格 |
| `row_span` | int 1-6 | 行跨度 |
| `grid_x` | int 0-3 | 网格列坐标 |
| `grid_y` | int | 网格行坐标 |
| `status` | enum | `draft` = 编辑中，`published` = 前台展示 |

### 预设尺寸

| 预设名 | col_span | row_span | 图标 | 适用场景 |
|--------|----------|----------|------|----------|
| 小卡片 | 1 | 1 | □ | 行情数据、单一指标 |
| 中方块 | 2 | 1 | □□ | 标准文章 |
| 大卡片 | 2 | 2 | □□<br>□□ | 重点内容、图表 |
| 宽横幅 | 4 | 1 | □□□□ | 列表、Top N |
| 全宽 | 4 | 2 | □□□□<br>□□□□ | 头条、精选 |

---

## 2. 发布机制（优化 A）

### 事务式覆盖写入

发布 API `POST /api/admin/pages/{route}/publish`：

```python
@router.post("/pages/{route:path}/publish")
def publish_page(route: str, session: Session = Depends(get_session)):
    # 1. 删除该页面的所有旧 published 记录
    session.execute(
        delete(PageBlock).where(
            PageBlock.page_route == route,
            PageBlock.status == "published"
        )
    )
    # 2. 读取所有 draft，复制并改为 published
    drafts = session.scalars(
        select(PageBlock).where(
            PageBlock.page_route == route,
            PageBlock.status == "draft"
        )
    ).all()
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
    session.commit()
    return {"published": True, "blocks": len(drafts)}
```

**设计要点：**
- 单事务完成，保证原子性
- Draft 中被删除的方块不会出现在 Published 中（数据孤岛消除）
- `block_key` 保持稳定，跨 draft/published 一致

---

## 3. 稳定标识（优化 B）

### `block_key` 字段

- 新建方块时，前端生成 UUID（`crypto.randomUUID()`），作为 `block_key` 传给后端
- 覆盖式发布时，同一个方块的 draft 和 published 记录共享相同的 `block_key`
- 前端渲染用 `block_key` 而非数据库 `id` 作为 React `key`

创建方块 API 增加 `block_key` 参数：

```python
class BlockCreate(BaseModel):
    # ... existing fields
    block_key: str = ""  # UUID, 前端生成
```

---

## 4. 画布编辑器交互

### 网格碰撞检测（优化 C）

**策略：阻挡回弹**

拖拽结束（`onDragStop`）时：

1. 计算新位置的网格区域 `(grid_x, grid_y, col_span, row_span)`
2. 遍历同页面其他方块，检查矩形是否重叠：

```ts
function hasCollision(a: Block, b: Block): boolean {
  return (
    a.grid_x < b.grid_x + b.col_span &&
    a.grid_x + a.col_span > b.grid_x &&
    a.grid_y < b.grid_y + b.row_span &&
    a.grid_y + a.row_span > b.grid_y
  );
}
```

3. 如果碰撞：方块回弹到拖拽前位置 + Toast 提示"该位置已有其他组件"

### 尺寸边界限制（优化 D）

| 属性 | 最小值 | 最大值 | 约束 |
|------|--------|--------|------|
| `col_span` | 1 | 4 | 不能超出画布总列数 |
| `row_span` | 1 | 6 | 硬编码上限 |
| `grid_x` | 0 | 3 | `grid_x + col_span <= 4` |

缩放时（`onResizeStop`）检查：
- 如果 `grid_x + col_span > 4`：不允许向右放大
- 如果 `col_span < 1`：不允许继续缩小
- 如果 `row_span < 1`：不允许继续缩小

### 画布界面结构

```
┌──────────────────────────────────────────┐
│  页面: [摘要页 ▼]  [编辑] [预览]  [发布]  │
├──────────────────────────────────────────┤
│  ┌──────┐ ┌──────────────┐              │
│  │ 小卡  │ │   宽横幅      │              │
│  │ 1x1  │ │   4x1        │              │
│  └──────┘ └──────────────┘              │
│  ┌──────────────┐ ┌──────┐             │
│  │   大卡片       │ │ 小卡  │             │
│  │   2x2        │ │ 1x1  │             │
│  └──────────────┘ └──────┘             │
│                                          │
│  [+ 添加方块]  ← 弹出预设选择器           │
└──────────────────────────────────────────┘
```

**工具栏：**
- `页面选择器`：切换编辑不同页面（摘要页 / 股票页 / 后续页面）
- `编辑 / 预览`：切换编辑模式（显示网格线、拖拽手柄）和预览模式（只看最终效果）
- `发布`：触发 publish API，成功后 Toast 提示

**方块交互：**
- 拖拽：鼠标按住方块头部工具栏拖拽，松手自动对齐网格
- 缩放：右下角三角形手柄，拖拽调整尺寸（吸附网格）
- 配置：点击方块 → 右侧滑出配置面板（数据源、条数、样式、预设尺寸）
- 删除：配置面板内的删除按钮，或方块右上角 X 按钮

---

## 5. 前台渲染

### 桌面端：CSS Grid 4 列

```css
.page-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px 16px;
}

.grid-item {
  grid-column: span var(--col-span);
  grid-row: span var(--row-span);
  min-height: 0;
}
```

每个方块通过 inline style 设置 `--col-span`、`--row-span`，Grid 自动流式排列（默认不设 `grid-row` / `grid-column` 固定位置，让浏览器自动流式排版，但保持方块的 `grid_x` / `grid_y` 用于排序）。

### 移动端响应式降级（优化 E）

```css
@media (max-width: 768px) {
  .page-grid {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .grid-item {
    width: 100% !important;
    grid-column: span 1 !important;
  }
}
```

前台 API 返回时按 `(grid_y ASC, grid_x ASC)` 排序，确保移动端从上到下的阅读顺序符合直觉。

### 骨架屏加载（优化 F）

前台页面渲染流程：

```
1. GET /api/public/pages/{route}/blocks → 返回区块配置（含 col_span, row_span 等）
2. 立即渲染 CSS Grid 布局外壳，每个方块显示 Skeleton 骨架屏
3. 每个方块独立异步请求自己的数据（或后端在 step 1 中已经聚合返回 data 字段）
4. 数据到达后替换骨架屏
```

当前架构是后端在 blocks API 中一次性聚合所有数据（`resolve_block_data`），所以天然不会白屏。骨架屏用于改善视觉效果：

```tsx
function BlockSkeleton({ colSpan, rowSpan }: { colSpan: number; rowSpan: number }) {
  return (
    <div className="animate-pulse bg-card rounded-xl border p-5" style={{ gridColumn: `span ${colSpan}`, gridRow: `span ${rowSpan}` }}>
      <div className="h-4 bg-muted rounded w-2/3 mb-3" />
      <div className="h-3 bg-muted rounded w-full mb-2" />
      <div className="h-3 bg-muted rounded w-4/5" />
    </div>
  );
}
```

---

## 6. 技术选型

| 层面 | 选型 |
|------|------|
| 拖拽画布 | `react-grid-layout` (GridLayout, Responsive, WidthProvider) |
| 网格碰撞 | 自定义 `hasCollision()` 函数 |
| 拖拽手柄 | `react-grid-layout` 内置 `dragHandle` |
| 缩放 | `react-grid-layout` 内置 `isResizable` |
| 前端 UUID | `crypto.randomUUID()` |
| 骨架屏 | Tailwind `animate-pulse` |

---

## 7. API 变更

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/admin/blocks?page_route=/&status=draft` | 获取草稿（返回 grid 布局字段） |
| `POST` | `/api/admin/blocks` | 创建方块（含 `block_key`、grid 字段） |
| `PUT` | `/api/admin/blocks/{id}` | 更新方块（含拖拽后新的 grid 位置） |
| `DELETE` | `/api/admin/blocks/{id}` | 删除方块 |
| `POST` | `/api/admin/pages/{route}/publish` | 发布页面（draft → published） |
| `GET` | `/api/public/pages/{route}/blocks` | 前台读取（只返回 `status=published`，含 grid 字段 + 聚合 data） |

---

## 8. 实施范围

### Phase 1: 数据模型 + 后端
- 迁移：`page_blocks` 加 `block_key`、`col_span`、`row_span`、`grid_x`、`grid_y`、`status` 列
- 发布 API
- 公开 API 支持 `status=published` 过滤 + 按 grid 排序
- 测试

### Phase 2: 画布编辑器
- 安装 `react-grid-layout`
- 重写 `/admin/layout` 页面为画布视图
- 碰撞检测 + 边界限制
- 预设尺寸选择器
- 配置侧面板
- Toast 交互反馈

### Phase 3: 前台渲染
- CSS Grid 布局
- 移动端响应式降级
- 骨架屏加载
