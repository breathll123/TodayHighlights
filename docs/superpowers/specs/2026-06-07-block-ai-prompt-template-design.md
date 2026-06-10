# 今日看点 区块 AI Prompt 模板设计

Date: 2026-06-07
Status: Written spec awaiting user review
Scope: 区块级 AI 分析的克制版 Prompt 模板架构

## 背景

今日看点的区块级 AI 分析会覆盖股票、AI、足球等不同主题，也会覆盖新闻、榜单、赛事等不同内容形态。如果只维护一个很长的 `BLOCK_ANALYSIS_SYSTEM_PROMPT`，后续每增加一个主题都要继续往提示词里追加规则，最终会变得难以维护。

本设计采用三层架构：

```text
source_type
  -> content_class      代码层，收敛为少量分析框架
  -> topic_context      数据库层，按 topic + content_class 配置领域语境
  -> runtime prompt     服务层，运行时组装最终 System Prompt
```

第一版保持克制：代码固定输出格式、通用禁止规则和三类分析框架；数据库只允许配置领域背景和额外禁令。

## 目标

- 让区块 AI 分析支持多主题，而不是只围绕股票写死。
- 将细碎的 `source_type` 收敛为少量 `content_class`。
- 新增主题时，优先通过后台配置领域语境，不改代码。
- 保持输出 JSON 结构、字段边界和禁止规则稳定。
- 避免 prompt 配置过度自由，降低线上配置把输出格式改坏的风险。

## 非目标

- 不做完整 Prompt 工作台。
- 不允许普通后台表单完全覆盖系统 Prompt。
- 不把 `_OUTPUT_SPEC`、通用禁止规则放进数据库。
- 不做 prompt A/B 测试。
- 不做 prompt 历史回滚 UI。
- 不改变现有 item/topic summary prompt。
- 不改变 AI 抽屉 UI、用户体系和 token usage 设计。

## 方案选择

选择方案 B：代码固定框架，数据库只存领域补充。

### 方案 A：单个硬编码 Prompt

继续维护一个长 `BLOCK_ANALYSIS_SYSTEM_PROMPT`。实现最简单，但多主题扩展后会变得臃肿，股票、足球、AI 的规则互相污染。

### 方案 B：代码固定框架，数据库只存领域补充

代码维护 `source_type -> content_class`、三类分析框架、输出规格和通用禁止规则。数据库按 `topic_slug + content_class` 存 `topic_context` 和 `extra_forbidden`。

这是本轮采用的方案。它保留足够扩展性，同时限制配置自由度。

### 方案 C：完整可配置 Prompt 平台

数据库可完全覆盖分析框架、输出规格和禁止规则。灵活性最高，但第一版风险过高，容易破坏 JSON 输出和服务端校验。

## content_class 设计

第一版只保留三类：

- `news`: 新闻、公告、快讯、技术资讯、AI 资讯。
- `rank`: 榜单、行情、指数、资金流、排行榜、积分榜。
- `event`: 赛程、赛果、比赛、发布会、明确时间节点事件。

默认规则：

- 未映射的 `source_type` 默认归入 `news`。
- 映射由代码维护，避免后台随意新增导致框架不可控。

建议初始映射：

```python
SOURCE_TYPE_TO_CLASS = {
    "tonghuashun_news": "news",
    "eastmoney_announcements": "news",
    "aihot_news": "news",

    "hot_stocks": "rank",
    "hot_events": "rank",
    "xueqiu_hot_cn": "rank",
    "xueqiu_hot_hk": "rank",
    "xueqiu_hot_us": "rank",
    "screener": "rank",
    "eastmoney_sectors": "rank",
    "eastmoney_industry": "rank",
    "eastmoney_indices": "rank",
    "eastmoney_capital_flow": "rank",
    "eastmoney_longhu": "rank",
    "qiumiwu_standings": "rank",
    "datalearner_leaderboard": "rank",
    "datalearner_aa_index": "rank",

    "qiumiwu_matches": "event",
    "qiumiwu_fixtures": "event",
    "qiumiwu_schedule": "event",
}
```

## Prompt 模板数据模型

新增 `ai_prompt_templates`：

- `id`
- `topic_slug`
- `content_class`: `news` / `rank` / `event`
- `topic_context`
- `extra_forbidden`
- `enabled`
- `template_version`
- `updated_by_user_id`
- `notes`
- `created_at`
- `updated_at`

约束：

- `topic_slug + content_class` 唯一。
- `topic_context` 用于领域背景和特殊分析角度。
- `extra_forbidden` 用于追加该领域专属禁令。
- `template_version` 每次编辑递增。
- `updated_by_user_id` 记录最近修改人。
- 第一版不加入 `override_framework` 字段，避免后台配置完全覆盖分析框架。

## 默认模板

迁移或初始化时可预置少量模板：

### stocks + news

```text
分析股票资讯时关注：政策信号、业绩变化、公告影响、板块联动和市场情绪。注意区分一次性事件和趋势性变化。
```

额外禁令：

```text
不得给出买入、卖出、持有、加仓、减仓等操作建议；不得给出价格预测、涨跌预测或收益承诺。
```

### stocks + rank

```text
分析股票榜单和行情时关注：资金集中度、板块联动、龙头效应、异常涨跌幅、成交或资金流变化。
```

额外禁令同股票资讯。

### football + event

```text
分析足球赛事时关注：赛果、比赛状态、时间节点、积分影响、排名变化、主客场因素和后续赛程。
```

额外禁令：

```text
不得预测比分，不得把未开赛比赛描述为已发生事实。
```

### football + rank

```text
分析足球积分榜或排行榜时关注：排名变化、积分差距、净胜球、晋级或保级压力、赛程影响。
```

### ai + news

```text
分析 AI 资讯时关注：模型能力变化、产品发布、商业化进展、开源与闭源格局、监管动态和产业影响。
```

## 代码层 Prompt 结构

代码固定以下部分：

- `_FRAMEWORKS`
- `_OUTPUT_SPEC`
- `_FORBIDDEN_BASE`
- `SOURCE_TYPE_TO_CLASS`
- `get_content_class(source_type)`
- `build_block_system_prompt(topic_slug, content_class, template)`

三类框架只描述“怎么分析”，不放具体领域知识。

### news 框架

```text
识别增量信息，排除重复和常规内容。
判断事件可能影响的对象、范围和路径。
将多个相关内容合并成更高层级看点。
指出信息不足、来源单一或前提不明确的地方。
```

### rank 框架

```text
识别数值、排名、资金、涨跌幅、积分等异常项。
判断异动是分散还是集中，集中在哪些方向。
总结当前结构反映的偏好、压力或变化。
指出延续或反转需要观察的后续信号。
```

### event 框架

```text
提取关键事实、时间、状态和结果。
判断事件对后续节奏、排名、赛程或相关主体的影响。
识别超预期、异常或值得关注的变化。
说明下一步值得关注的关键节点。
```

### 输出规格

输出 JSON 字段固定：

- `summary_points`: 1-4 条，每条最多 160 字。
- `key_changes`: 0-3 条，每条最多 140 字。
- `risk_points`: 0-2 条，每条最多 140 字。
- `related_entities`: 0-8 个，每个最多 40 字。
- `confidence`: 0 到 1。

服务端校验仍是最终边界。Prompt 不能代替后端校验。

## 运行时组装

区块分析生成前：

1. 根据 `block.source_type` 得到 `content_class`。
2. 从 `page_route` 推导 `topic_slug`：
   - `/topics/stocks` -> `stocks`
   - `/topics/football` -> `football`
   - `/topics/ai` -> `ai`
   - `/` 或无法识别时使用 `summary`
3. 查询启用的 `ai_prompt_templates`。
4. 用代码框架 + 输出规格 + 通用禁止规则 + 数据库领域上下文 + 数据库额外禁令组装最终 System Prompt。
5. 无模板时只使用代码默认框架。

组装顺序：

```text
角色说明
领域背景 topic_context
content_class 分析框架
输出规格
通用禁止规则
额外禁止规则 extra_forbidden
```

## 后台管理

新增管理员接口：

- `GET /api/admin/ai-prompt-templates`
- `POST /api/admin/ai-prompt-templates`
- `PUT /api/admin/ai-prompt-templates/{id}`
- `DELETE /api/admin/ai-prompt-templates/{id}`

后台页面第一版只做轻量表单：

- `topic_slug`
- `content_class`
- `topic_context`
- `extra_forbidden`
- `enabled`
- `notes`

不暴露完整 framework override。

## 错误与降级

- 未找到模板：使用代码默认框架。
- 模板被禁用：使用代码默认框架。
- `topic_context` 为空：不注入领域背景段。
- `extra_forbidden` 为空：只使用通用禁止规则。
- `content_class` 无效：回退 `news`。
- 数据库查询失败：记录错误并使用默认 prompt，不能阻塞区块分析。

## 测试策略

后端测试：

- `get_content_class` 覆盖现有 source_type。
- 未知 source_type 回退 `news`。
- `build_block_system_prompt` 在无模板时使用默认框架。
- 有模板时注入 `topic_context` 和 `extra_forbidden`。
- 禁用模板不参与组装。
- `/topics/stocks`、`/topics/football`、`/topics/ai` 的 topic_slug 推导正确。
- `ai_prompt_templates` 唯一约束生效。
- 后台 CRUD 只有管理员可访问。

前端测试：

- Prompt 模板管理页能展示模板列表。
- 新建和编辑表单包含 topic_slug、content_class、topic_context、extra_forbidden、enabled。
- 不展示 override_framework 输入。

手动验证：

- 给 `ai + news` 新增 topic_context 后，下一次 AI 资讯区块分析使用新领域背景。
- 禁用模板后，分析回退默认框架。
- 股票模板不会影响足球和 AI 页面。

