# 前端模块管理系统设计

> 将前端公开页面从硬编码渲染改为数据库驱动的可配置内容区块系统，同时升级前端技术栈。

---

## 动机

当前公开页面（摘要页 `/`、股票页 `/topics/stocks`）的内容逻辑硬编码在前端组件中——直接调 `fetchHighlights()` 渲染全部非隐藏看点。管理者无法灵活调整每个页面展示什么、以什么顺序展示、从哪个数据源获取数据。

## 目标

- 新增 `page_blocks` 数据库表，描述每个页面的内容区块配置
- 新增管理后台「页面布局」页面，支持区块 CRUD 和拖拽排序
- 改造公开页面为动态渲染：根据路由加载对应区块配置，每个区块独立请求数据
- 前端技术栈升级到 Tailwind + shadcn/ui + Axios + Zustand

---

## 数据模型

### 新表：`page_blocks`

```sql
CREATE TABLE page_blocks (
    id              INTEGER PRIMARY KEY AUTO_INCREMENT,
    page_route      VARCHAR(80)  NOT NULL,       -- "/" , "/topics/stocks"
    title           VARCHAR(120) NOT NULL,        -- "今日热股"
    sort_order      INTEGER      NOT NULL DEFAULT 0,
    source_type     VARCHAR(40)  NOT NULL,        -- topic | search | hot_stocks | hot_events | screener
    source_config   JSON         NOT NULL,        -- 来源配置（按 source_type 不同）
    display_style   VARCHAR(40)  NOT NULL DEFAULT 'card',  -- card | list
    display_count   INTEGER      NOT NULL DEFAULT 5,
    sort_by         VARCHAR(40)  NOT NULL DEFAULT 'created_at',  -- score | created_at
    enabled         BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### `source_config` 结构

| source_type | source_config 示例 | 说明 |
|-------------|-------------------|------|
| `topic` | `{"topic_id": 1}` | 从指定话题的 highlights 取数据 |
| `search` | `{"query": "芯片", "count": 20}` | 调用雪球搜索，count 为抓取条数 |
| `hot_stocks` | `{"type": 10}` | type=10 A股热度榜，type=11 美股 |
| `hot_events` | `{}` | 热门话题（无需参数） |
| `screener` | `{"order_by": "percent", "size": 20}` | 活跃股票筛选 |

### 迁移文件

在 `backend/migrations/versions/` 下新增 `20260522_0002_page_blocks.py`。

---

## 后端 API

### 公开 API

**`GET /api/public/pages/{route}/blocks`**

返回指定路由上所有启用区块的数据。响应格式：

```json
{
  "blocks": [
    {
      "id": 1,
      "title": "今日热股",
      "sort_order": 0,
      "display_style": "card",
      "display_count": 5,
      "source_type": "hot_stocks",
      "data": [
        {"code": "SZ000725", "name": "京东方A", "current": 5.16, "percent": 10.02}
      ]
    }
  ]
}
```

每个区块的 `data` 字段由后端根据 `source_type` 和 `source_config` 实时查询填充。

数据获取逻辑按 source_type 分支：

| source_type | 数据获取方式 |
|-------------|-------------|
| `topic` | `SELECT * FROM highlights WHERE topic_id=X AND is_hidden=0 ORDER BY is_pinned DESC, score DESC LIMIT N` |
| `search` | 调用 `XueqiuAdapter.fetch()` → 写入 raw_items → 生成 highlights → 返回 highlights |
| `hot_stocks` | 代理请求 `stock.xueqiu.com/v5/stock/hot_stock/list.json` → 映射字段返回 |
| `hot_events` | 代理请求 `xueqiu.com/hot_event/list.json` → 映射字段返回 |
| `screener` | 代理请求 `xueqiu.com/service/screener/quote/list` → 映射字段返回 |

> 对于 `search`、`hot_stocks`、`hot_events`、`screener`，首次请求时后端代为请求雪球 API 并缓存到 raw_items，后续请求优先从本地数据库读取。

### 管理后台 API

```
GET    /api/admin/blocks              → 所有区块列表（可按 page_route 过滤）
POST   /api/admin/blocks              → 创建区块
PUT    /api/admin/blocks/{id}         → 更新区块
DELETE /api/admin/blocks/{id}         → 删除区块
PATCH  /api/admin/blocks/reorder      → 批量更新排序 { "items": [{"id": 1, "sort_order": 0}, ...] }
```

**Schema（创建/更新）：**

```python
class BlockCreate(BaseModel):
    page_route: str
    title: str
    sort_order: int = 0
    source_type: str
    source_config: dict
    display_style: str = "card"
    display_count: int = 5
    sort_by: str = "created_at"
    enabled: bool = True
```

---

## 前端技术栈升级

### 旧 → 新

| 层面 | 旧 | 新 |
|------|-----|-----|
| 样式 | 全局 `styles.css` | Tailwind CSS v3 + CSS Variables (HSL) |
| 组件库 | 无 | shadcn/ui (Button, Dialog, Dropdown, Slider, Tabs) |
| 图标 | 无 | Lucide React |
| 状态 | TanStack Query | TanStack Query (服务端) + React Context (UI 状态) |
| HTTP | fetch | Axios (拦截器 / 统一错误处理) |
| 动画 | 无 | framer-motion |
| 图表 | 无 | recharts |
| 主题 | 无 | next-themes (深色/浅色) |
| Toast | 无 | sonner |
| Markdown | 无 | react-markdown + remark-gfm |
| 工具 | 无 | clsx + tailwind-merge + cva |

### 项目结构（升级后）

```
frontend/
  index.html
  package.json
  vite.config.ts
  tailwind.config.ts
  components.json              ← shadcn/ui 配置
  src/
    main.tsx
    App.tsx
    api/
      client.ts                ← Axios 实例 + 拦截器
      types.ts
    components/
      ui/                      ← shadcn/ui 组件
        button.tsx
        card.tsx
        dialog.tsx
        dropdown-menu.tsx
        tabs.tsx
        slider.tsx
        input.tsx
        textarea.tsx
        select.tsx
        switch.tsx
        separator.tsx
        scroll-area.tsx
      layout/
        Navbar.tsx
        BlockCard.tsx           ← 公开页面区块卡片
        BlockCardSkeleton.tsx
      admin/
        AdminSidebar.tsx
        BlockEditor.tsx         ← 区块编辑抽屉/Modal
        SortableBlockItem.tsx   ← 可拖拽排序项
    pages/
      SummaryPage.tsx           ← 改为 PageRenderer
      StockTopicPage.tsx
      AdminSourcesPage.tsx
      AdminJobsPage.tsx
      AdminHighlightsPage.tsx
      AdminSettingsPage.tsx
      AdminLayoutPage.tsx       ← 新：页面布局管理
    hooks/
      use-page-blocks.ts
    lib/
      utils.ts                  ← clsx + twMerge
    styles/
      globals.css               ← Tailwind 指令 + CSS Variables
    __tests__/
      ...
```

---

## 新管理页面：页面布局 (`/admin/layout`)

### 布局

```
┌──────────────────────────────────────────┐
│  管理后台导航                             │
│  [数据源] [任务] [看点] [设置] [布局]     │
├────────────┬─────────────────────────────┤
│  页面列表   │                             │
│            │   区块列表（可拖拽排序）       │
│  ● 摘要页 /│  ┌───────────────────────┐  │
│    股票页   │  │ ≡ 今日热股  [卡片] [5]│  │
│  ○ AI      │  │   来源: hot_stocks    │  │
│  ○ 足球    │  │   [编辑] [删除] [开关] │  │
│            │  └───────────────────────┘  │
│            │  ┌───────────────────────┐  │
│            │  │ ≡ 热门话题  [卡片] [10]│  │
│            │  │   来源: hot_events     │  │
│            │  │   [编辑] [删除] [开关] │  │
│            │  └───────────────────────┘  │
│            │                             │
│            │  [+ 添加区块]               │
└────────────┴─────────────────────────────┘
```

### 交互

- 左侧页面列表可新增/编辑/删除页面（未来扩展），当前固定「摘要页」「股票页」
- 点击页面 → 右侧显示该页面的区块列表
- 区块卡片拖拽排序（`onDragEnd` → PATCH `/reorder`）
- 点击「编辑」→ 弹出 Dialog，包含：
  - 标题 (Input)
  - 来源类型 (Select: topic / search / hot_stocks / hot_events / screener)
  - 来源配置 (动态表单：根据 source_type 显示不同字段)
  - 展示形式 (Select: card / list)
  - 显示条数 (Slider / Input number)
  - 排序方式 (Select: score / created_at)
- 开关控制启用/禁用（Switch）
- 删除需确认（Dialog）

---

## 公开页面改造

### `PageRenderer` 组件

```tsx
// 用法：<PageRenderer route="/" />

function PageRenderer({ route }: { route: string }) {
  const { blocks, isLoading } = usePageBlocks(route);

  if (isLoading) return <Skeleton />;

  return (
    <div className="space-y-6">
      {blocks.map((block) => (
        <BlockSection key={block.id} block={block} />
      ))}
    </div>
  );
}
```

每个 `BlockSection` 根据 `block.display_style` 选择卡片/列表布局。

### 数据流

```
PageRenderer
  → GET /api/public/pages/{route}/blocks
  → 遍历 blocks
  → 直接渲染（data 已由后端填充）
```

公开页面不再直接调 `fetchHighlights()` 或雪球 API。所有数据在后端 `/api/public/pages/{route}/blocks` 内部完成聚合。

---

## 主题系统

使用 `next-themes` + CSS Variables (HSL)：

```css
:root {
  --background: 0 0% 100%;
  --foreground: 0 0% 3.9%;
  --card: 0 0% 100%;
  --primary: 220 70% 50%;
  --muted: 0 0% 96%;
  --border: 0 0% 89.8%;
}

.dark {
  --background: 0 0% 3.9%;
  --foreground: 0 0% 98%;
  --card: 0 0% 6%;
  --primary: 220 70% 60%;
  --muted: 0 0% 14.9%;
  --border: 0 0% 14.9%;
}
```

shadcn/ui 组件原生支持此主题系统。

---

## 实施策略

分阶段实施，每个阶段独立提交：

### Phase 1: 前端技术栈升级

1. 初始化 Tailwind + shadcn/ui 配置
2. 引入 Axios 替换 fetch
3. 改造现有组件（Navbar、页面、表单）为 Tailwind + shadcn/ui
4. 添加深色/浅色主题切换
5. 验证现有测试通过

### Phase 2: 后端 page_blocks

1. 创建迁移文件
2. 添加 SQLAlchemy 模型
3. 实现管理后台 CRUD API
4. 实现公开 API（含数据聚合逻辑）
5. 编写测试

### Phase 3: 管理后台布局页

1. 创建 `AdminLayoutPage.tsx`
2. 实现区块列表、创建/编辑 Dialog、拖拽排序
3. 实现动态表单（根据 source_type 切换配置项）

### Phase 4: 公开页面改造

1. 创建 `PageRenderer` + `BlockSection` 组件
2. 改造 `SummaryPage` 和 `StockTopicPage`
3. 实现各 source_type 的 Block 渲染变体

### Phase 5: 数据缓存

1. 为 hot_stocks / hot_events / screener 添加 raw_items 缓存逻辑
2. 添加定时刷新机制
3. 防止重复请求雪球 API

---

## 自检清单

- 范围控制：
  - 第一版只做 `topic` 和 `hot_stocks` 两种 source_type 的数据聚合
  - `search`、`hot_events`、`screener` 的适配器留到后续迭代
  - 页面列表固定为摘要页 + 股票页，不实现页面 CRUD
  - 展示形式只做 `card`，`list` 预留
- 敏感数据：source_config 不包含 Cookie/API Key
- 测试：API CRUD 测试 + 前端 BlockSection 渲染测试
