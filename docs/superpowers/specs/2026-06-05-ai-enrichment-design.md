# DataFlow AI 赋能设计

Date: 2026-06-05
Status: Written spec awaiting user review
Scope: 通用 AI 加工架构，首批只在股票主题启用

## 背景

DataFlow 已经从单一股票看板扩展为多主题信息聚合平台，当前包含股票、AI、足球等主题。现有架构具备独立 source adapter、`raw_items` 原始内容存储、`highlights` 看点展示、`page_blocks` 页面布局配置，以及后台模型设置和 Fernet 加密能力。

这次 AI 赋能的目标不是做聊天机器人，而是先让系统把已采集的数据加工成更容易阅读、管理和展示的内容。

## 目标

首版采用“单条内容先加工，再汇总成主题级今日看点”的方式：

```text
raw_items
  -> 规则过滤/去重
  -> AI 候选池
  -> 单条 AI 加工
  -> 主题级今日看点
  -> 公开页展示
```

能力按通用架构设计，但首批只开启股票主题。后续可扩展到 AI、足球等主题。

## 首批范围

股票主题首批覆盖两类内容：

1. 资讯/公告类
   - 同花顺快讯、东方财富公告、雪球内容等。
   - 生成单条摘要、标签、重要性评分、关注点、风险点。
   - 成功后同步进入现有 `highlights`，供公开页和后台看点管理复用。

2. 榜单/行情类
   - 热股、板块、资金流、龙虎榜等。
   - 不对每一条强行生成摘要。
   - 只筛选明显异动项，作为主题级今日看点的上下文输入。

不在首版范围：

- 不覆盖 AI/足球主题。
- 不做自然语言问答。
- 不做多模型用途路由、模型对比或模型评分。
- 不做买卖建议、价格预测、确定性投资结论。

## AI 文案边界

股票内容允许生成：

- 中性摘要。
- 影响解读。
- 关注点。
- 风险提示。
- 涉及标的、板块、主题标签。

禁止生成：

- 买入、卖出、持有等操作建议。
- 价格预测、涨跌预测。
- “必然”“确定”“强烈推荐”等确定性结论。
- 暗示收益承诺的文案。

公开页 AI 模块需要显示轻量提示，例如“AI 摘要，仅供信息参考”。

## 方案选择

选择方案 B：股票 AI 看点层。

### 方案 A：最小闭环

只做股票资讯/公告单条 AI 摘要，生成后进入 `highlights`，公开页顶部展示“AI 今日看点”。

优点是快，风险低。缺点是榜单和行情不会参与汇总，看点容易变成普通新闻摘要。

### 方案 B：股票 AI 看点层

做通用 AI 加工架构，首批只启用股票。资讯/公告做单条摘要；榜单/行情只筛明显异动项参与主题级今日看点；公开页顶部展示“AI 今日看点”，区块内展示单条摘要和标签。

这是推荐并已确认的方案。它能体现 DataFlow 的核心价值：从很多数据里提炼“今天值得看什么”。

### 方案 C：完整 AI 运营平台

在方案 B 基础上增加完整 AI 工作台、候选池、模型对比、批量审核和多主题开关。

首版不采用该方案，因为范围过大，会延迟实际可见价值。

## 数据模型设计

### AI 模型配置

新增模型配置列表，替代当前单模型设置形态。模型数量预计不多，但需要支持后台新增和编辑。

新增 `ai_model_configs`：

- `id`
- `name`
- `base_url`
- `model`
- `api_key_encrypted`
- `is_default`
- `enabled`
- `notes`
- `created_at`
- `updated_at`

设计约束：

- API Key 使用现有 `CryptoService` Fernet 加密。
- 读取列表时只返回 `has_api_key`，不回传密钥明文。
- 首版只允许一个默认启用模型。
- 开发和测试环境允许 Mock 模型客户端，避免本地调试依赖外部网络。

### 单条 AI 加工结果

新增单条加工结果表，保留生成过程和追溯信息，不把所有生成字段直接塞进 `highlights`。

新增 `ai_item_enrichments`：

- `id`
- `topic_id`
- `raw_item_id`
- `status`: `pending` / `processing` / `generated` / `failed` / `hidden`
- `generated_title`
- `summary`
- `tags_json`
- `related_symbols_json`
- `importance_score`
- `focus_points_json`
- `risk_points_json`
- `model_config_id`
- `generated_by_model`
- `error_message`
- `retry_count`
- `last_attempted_at`
- `generated_at`
- `created_at`
- `updated_at`

约束：

- 同一个 `raw_item_id` 首版只保留一条当前有效加工结果。
- 初始生成 `retry_count = 0`，每次重试递增。
- 自动重试和后台手动重试共用 `retry_count`，`retry_count >= 3` 后后台不再允许继续重试，除非后续单独增加“重置重试次数”能力。
- 每次尝试模型调用前更新 `last_attempted_at`。
- 生成成功后同步创建或更新 `highlights`。
- AI 失败不影响原始数据保存和公开页原始内容展示。

### 主题级今日看点

新增主题级汇总表，承载顶部“AI 今日看点”模块。

新增 `ai_topic_summaries`：

- `id`
- `topic_id`
- `summary_date`
- `version`
- `status`: `generated` / `failed` / `hidden`
- `title`
- `items_json`: 3-5 条看点，每条包含标题、原因、涉及标的/板块、风险提示、引用来源 ID
- `source_refs_json`
- `model_config_id`
- `generated_by_model`
- `error_message`
- `generated_at`
- `created_at`
- `updated_at`

版本规则：

- 同一个 `topic_id + summary_date` 可以有多个版本。
- 定时任务生成当天第一个版本时使用 `version = 1`。
- 后台手动重新生成时新增一条记录，`version` 递增，不覆盖旧记录。
- 公开页读取同一主题下最新 `generated` 且未隐藏的最高版本。
- 后续如果需要回滚，只需要把旧版本恢复为可展示状态；首版后台不做回滚 UI。

### 生成日志

首版需要轻量日志，不做完整 AI 工作台。

新增 `ai_generation_jobs`，供 `/admin/ai-jobs` 查询：

- `id`
- `job_type`: `item_enrichment` / `topic_summary`
- `trigger_type`: `crawl` / `scheduled` / `manual` / `retry`
- `topic_id`
- `raw_item_id`
- `item_enrichment_id`
- `topic_summary_id`
- `model_config_id`
- `status`: `pending` / `processing` / `succeeded` / `failed` / `partial`
- `input_count`
- `success_count`
- `failed_count`
- `retry_of_job_id`
- `error_message`
- `log_excerpt`
- `started_at`
- `finished_at`
- `created_at`

约束：

- 单条重试任务通过 `retry_of_job_id` 指向原失败任务。
- 批处理里部分候选失败时，任务状态为 `partial`，成功项仍保存。
- `/admin/ai-jobs` 展示最近任务、失败原因、重试入口和当前默认模型状态。

## 候选筛选规则

首版候选筛选采用确定性规则，不使用语义相似度，避免联调阶段出现不可复现结果。

### 单条加工候选

适用范围：

- 股票主题下资讯、公告、快讯、雪球内容等文本型 `raw_items`。
- 榜单、行情、比分等结构化数据不进入单条加工候选。

时间窗口：

- 只处理 `published_at` 或 `created_at` 在最近 24 小时内的 `raw_items`。
- 爬虫触发时优先处理本次保存的新内容。
- 定时补偿任务最多回扫最近 24 小时未处理内容。

内容长度：

- 标题去空白后少于 6 个字符时跳过。
- `title + body` 归一化后少于 40 个字符时跳过。
- 正文过长时截取前 4,000 个字符作为模型输入，原始内容仍完整保留在 `raw_items`。

去重：

- `raw_items` 继续使用现有 `source_id + external_id` 和 `source_id + content_hash` 唯一约束。
- AI 候选层额外跳过已经存在 `ai_item_enrichments` 的 `raw_item_id`。
- 同一 topic、同一 24 小时窗口内，归一化标题完全相同的内容只处理发布时间最新的一条。
- 首版不做标题相似度和语义相似度去重。

批处理上限：

- 单次爬虫触发最多创建 50 个单条加工候选。
- 定时补偿任务单批最多处理 200 个候选。
- 超出上限的候选留到下一轮，按 `published_at` 倒序处理。

### 主题汇总上下文

主题级今日看点输入由两部分组成：

- 最近 24 小时内 `status = generated` 且 `importance_score >= 60` 的单条加工结果，最多 30 条。
- 最近 24 小时内明显榜单/行情异动项，最多 20 条。

榜单/行情异动首版规则：

- 热股、板块、资金流、龙虎榜等 source type 可作为异动来源。
- 优先选择原始数据中排名前 10、涨跌幅绝对值明显、资金流字段靠前、或龙虎榜成交/买卖额靠前的项目。
- 具体字段按各 source adapter 已暴露 metrics 映射，无法识别数值字段时只使用排名前 10。

## 生成任务

### 单条 AI 加工

触发时机：

- 爬虫保存 `raw_items` 后，对股票主题数据执行候选筛选。
- 符合条件的候选内容进入 AI 加工任务。

流程：

1. 读取股票主题下新保存的 `raw_items`。
2. 按 source type、时间、去重、关键词、内容长度和批处理上限筛出候选。
3. 创建 `ai_item_enrichments` pending 记录。
4. 后台任务调用默认模型生成结构化 JSON。
5. 校验 JSON。
6. 保存加工结果。
7. 同步 `highlights`。

失败处理：

- 模型不可用：记录 failed，不影响爬虫。
- JSON 不合法：记录 failed，不展示半成品。
- API Key 未配置：跳过生成，后台提示未配置。
- 重试次数达到 3 次：保持 failed，后台隐藏重试按钮或置灰。

### 主题级今日看点

触发时机：

- 定时批处理。
- 可支持后台手动重新生成。

流程：

1. 读取最近 24 小时的股票 `ai_item_enrichments`。
2. 读取明显榜单/行情异动项作为上下文。
3. 生成 3-5 条主题级看点。
4. 保存到 `ai_topic_summaries`。
5. 公开页顶部读取最新可展示版本。

## 后台设计

### 模型设置

将 `/admin/settings` 从单模型表单升级为模型配置列表：

- 列表展示名称、base URL、model、默认状态、启用状态、API Key 状态。
- 新增/编辑表单支持维护 base URL、model、API Key、备注。
- API Key 留空表示不修改已保存密钥。
- 设为默认时，服务端负责取消其他默认模型。

### 看点管理

复用现有 `/admin/highlights`：

- AI 生成看点自动展示。
- 后台可以编辑标题和摘要。
- 后台可以隐藏或置顶。
- `review_status` 可继续标识 generated/reviewed。

### AI 生成日志

新增轻量入口，例如 `/admin/ai-jobs`：

- 查看最近生成任务。
- 查看失败原因。
- 触发重试。
- 查看当前默认模型和 API Key 状态。

首版不做完整候选池 UI。

## 公开页展示

股票页采用“顶部今日看点 + 区块内增强”。

### 顶部 AI 今日看点

显示位置：

- 股票主题页顶部，位于原有 page blocks 之前。

内容：

- 3-5 条重点。
- 每条包含简短原因、涉及标的/板块、风险提示。
- 显示生成时间。
- 显示“AI 摘要，仅供信息参考”提示。

状态：

- 没有模型配置或没有生成结果时隐藏，不影响原页面。
- 生成失败时不在公开页显示失败信息。
- 请求加载中时只显示一个轻量骨架区，不阻塞原有 page blocks 渲染。
- 请求失败时隐藏顶部 AI 今日看点，不显示错误 toast。

### 区块内增强

资讯、公告、快讯类区块满足以下条件时显示 AI 增强：

- 对应 `raw_item_id` 存在 `ai_item_enrichments`。
- `status = generated`。
- `importance_score >= 40`。
- 结果未被隐藏。

显示内容：

- AI 摘要。
- 标签。
- 重要性评分。
- 原文链接。

降级：

- 没有加工结果时显示原始内容。
- 加工状态为 `pending` 或 `processing` 时显示原始内容，不显示行内 loading。
- 加工状态为 `failed` 时显示原始内容，不显示失败信息。
- 加工状态为 `hidden` 时显示原始内容，不显示 AI 摘要和标签。

榜单、行情类区块首版不逐条显示 AI 摘要，只参与顶部汇总。

## API 设计

新增或调整以下接口：

- `GET /api/admin/ai-models`
- `POST /api/admin/ai-models`
- `PUT /api/admin/ai-models/{id}`
- `DELETE /api/admin/ai-models/{id}`
- `POST /api/admin/ai-models/{id}/set-default`
- `GET /api/admin/ai-jobs`
- `POST /api/admin/ai-jobs/{id}/retry`
- `POST /api/admin/ai/topic-summaries/stocks/regenerate`
- `GET /api/public/topics/{slug}/ai-summary`

首版公开页使用独立的 `GET /api/public/topics/{slug}/ai-summary` 请求顶部 AI 今日看点，不改变现有 page blocks 数据结构。

## Prompt 输出结构

### 单条加工 Prompt 草稿

System:

```text
你是 DataFlow 的股票信息整理助手。你的任务是把输入内容整理成中性、可读、可追溯的信息摘要。
你可以说明事件、影响解读、关注点和风险提示。
你必须避免买入、卖出、持有等操作建议，避免价格预测和涨跌预测，避免“必然”“确定”“强烈推荐”等确定性表达。
只输出合法 JSON，不输出 Markdown，不输出额外解释。
```

User:

```text
请基于以下股票主题内容生成结构化摘要。

输出字段：
- title: 简短标题
- summary: 中性摘要
- tags: 主题标签
- related_symbols: 涉及标的或板块，可为空
- importance_score: 0 到 100 的重要性评分
- focus_points: 为什么值得关注
- risk_points: 需要注意的不确定性

内容：
标题：{title}
来源：{source_name}
发布时间：{published_at}
正文：{body}
```

单条加工要求模型输出 JSON：

```json
{
  "title": "简短标题",
  "summary": "中性摘要",
  "tags": ["标签"],
  "related_symbols": ["可为空"],
  "importance_score": 72,
  "focus_points": ["为什么值得关注"],
  "risk_points": ["需要注意的不确定性"]
}
```

### 主题汇总 Prompt 草稿

System:

```text
你是 DataFlow 的股票今日看点编辑助手。你的任务是从已加工摘要和市场异动上下文中提炼 3 到 5 条今日重点。
你可以做影响解读和风险提示，但不能输出买卖建议、价格预测、涨跌预测或确定性投资结论。
每条看点都应说明为什么重要，并保留引用来源 ID。
只输出合法 JSON，不输出 Markdown，不输出额外解释。
```

User:

```text
请基于以下股票主题上下文生成今日看点。

输入包含：
1. 单条 AI 加工结果列表
2. 榜单/行情异动列表

输出字段：
- title: 今日看点标题
- items: 3 到 5 条看点

上下文：
{context_json}
```

主题汇总要求模型输出 JSON：

```json
{
  "title": "股票今日看点",
  "items": [
    {
      "title": "看点标题",
      "reason": "为什么重要",
      "related": ["标的或板块"],
      "risk": "风险提示",
      "source_refs": [123, 456]
    }
  ]
}
```

### 服务端校验边界

服务端必须校验字段类型和长度，不能直接信任模型输出。

单条加工边界：

- `title`: 字符串，1-60 个字符。
- `summary`: 字符串，20-180 个字符。
- `tags`: 字符串数组，最多 5 个，每个 1-12 个字符。
- `related_symbols`: 字符串数组，最多 10 个，每个 1-20 个字符。
- `importance_score`: 整数，范围 0-100。
- `focus_points`: 字符串数组，1-3 条，每条 1-80 个字符。
- `risk_points`: 字符串数组，0-3 条，每条 1-80 个字符。

主题汇总边界：

- `title`: 字符串，1-40 个字符。
- `items`: 数组，3-5 条。
- `items[].title`: 字符串，1-60 个字符。
- `items[].reason`: 字符串，20-120 个字符。
- `items[].related`: 字符串数组，最多 8 个，每个 1-20 个字符。
- `items[].risk`: 字符串，0-100 个字符。
- `items[].source_refs`: 整数数组，最多 10 个。

校验失败处理：

- 字段缺失、类型错误、长度越界或 JSON 解析失败时，生成状态记为 `failed`。
- 不对越界内容做静默截断，避免展示被截断后语义不完整的 AI 文案。
- 失败原因写入 `ai_generation_jobs.error_message` 和对应结果表的 `error_message`。

## 测试策略

后端：

- 模型配置 CRUD，API Key 加密和不回传明文。
- 只允许一个默认模型。
- 候选筛选规则。
- 候选时间窗口、内容长度、去重和批处理上限。
- Mock 模型客户端生成单条加工结果。
- 生成失败时状态和错误记录。
- 重试次数、`last_attempted_at` 和重试上限。
- 主题级汇总生成和公开读取。
- 同日手动重新生成时版本递增，不覆盖旧版本。
- Prompt 输出校验边界，包含 score、summary、tags、focus/risk points 的长度和数量。

前端：

- 模型配置列表和表单。
- API Key 已配置/未配置状态。
- AI 今日看点模块有数据、无数据、加载、错误状态。
- 区块内 AI 摘要和标签展示。
- 区块内增强只在 `generated`、未隐藏、`importance_score >= 40` 时出现。
- 生成失败或隐藏时回退显示原始内容。

集成：

- 使用 Mock 模型跑通“raw_items -> enrichment -> highlights -> public page”链路。
- 模型不可用时公开页仍显示原始数据。

## 成功标准

- 后台可以添加和编辑多个模型配置，密钥加密保存。
- 股票主题资讯/公告可以生成单条 AI 摘要、标签、评分。
- AI 加工结果能自动同步到现有看点展示体系。
- 股票页顶部能展示主题级 AI 今日看点。
- 榜单/行情异动能参与主题级汇总，但不强制逐条摘要。
- 没有模型或模型失败时，公开页仍可正常展示原始数据。

## 后续扩展

- 为 AI、足球主题启用同一套 AI 加工能力。
- 按主题或用途绑定不同模型。
- 建立完整 AI 工作台，管理候选池、批量生成、失败重试和人工审核。
- 增加自然语言问答能力。
- 增加成本统计和 token 用量记录。
