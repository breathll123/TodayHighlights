# DataFlow 区块级 AI 分析与用户用量设计

Date: 2026-06-05
Status: Written spec awaiting user review
Scope: 登录用户使用公开页区块级 AI 分析，管理员查看 token 用量

## 背景

DataFlow 当前已经有股票、AI、足球等公开主题页，也已有管理员登录、AI 模型配置、单条内容 AI 加工、主题级今日看点和 AI 任务日志。

现有公开页的问题是信息密度偏高。用户需要的是“看某个方块时，可以按需让 AI 帮忙提炼”，而不是再增加一个默认展开的大型总结区域。因此本轮新增能力采用区块级 AI 分析：每个页面方块可以触发一次按需分析，结果显示在统一抽屉里，不改变原页面布局。

同时，后续如果公开部署给其他人使用，AI 调用会产生模型成本。用户已确认：想使用 AI 功能必须注册、登录，并按用户记录每次调用的 token 使用量。管理员可以根据使用情况切换模型，例如将高消耗场景或用户切到免费模型。

## 目标

- 公开页仍可匿名浏览基础内容。
- AI 分析必须登录后使用。
- 每个页面方块提供按需 `AI 分析` 入口。
- AI 分析结果在右侧抽屉展示，移动端使用底部 Sheet。
- 分析结果基于当前方块实际展示的数据生成，并使用缓存减少重复调用。
- 真实模型调用时记录用户、模型、场景和 token 使用量。
- 管理员可以查看用户 AI 用量，并禁用用户。

## 非目标

- 不做顶部市场趋势图，本轮后续再单独设计。
- 不做聊天机器人或自由问答。
- 不做游客免费次数。
- 不做第三方 OAuth、邮箱验证、验证码。
- 不做用户自带 API Key。
- 不做流式输出。
- 不做完整计费、套餐、支付或 SaaS 订阅。
- 不改变现有页面方块的数据来源和布局编辑能力。

## 方案选择

选择方案 B：普通用户注册登录 + AI 用量记录。

### 方案 A：只做管理员 AI

只有管理员登录后可以使用 AI。实现最快，但后续公开给其他人使用时还要重做普通用户体系。

### 方案 B：普通用户注册登录 + AI 用量记录

公开页面可以浏览，AI 分析必须登录。每次真实调用模型都记录用户、模型、token、场景和状态。管理员可以查看谁用得多，后续也可以切换模型或禁用用户。

这是本轮采用的方案。

### 方案 C：完整 SaaS 化

用户自己配置 API Key、选择模型、查看账单和额度。长期可能需要，但当前范围过大。

## 用户与权限

新增普通用户体系，并保留管理员角色。

### 角色

- `admin`: 可以进入后台、配置模型、管理用户、查看 token 用量、强制重新分析。
- `user`: 可以登录后使用公开页 AI 分析，不能进入后台。
- 未登录用户: 可以浏览公开页基础内容，不能使用 AI 分析。

### 注册和登录

首版采用用户名或邮箱加密码注册登录：

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`

注册默认开放。新用户默认角色为 `user`，状态为 `active`。

管理员可以禁用用户。被禁用用户不能登录，也不能触发 AI 分析。

### 管理员兼容策略

现有系统只有管理员密码和管理员 token。升级时需要避免用户无法进入后台：

- 新增 `users` 表。
- 初始化或迁移一个默认管理员用户。
- 短期可以保留旧 `/api/admin/login`，但推荐前端迁移到统一 `/api/auth/login`。
- 新 token payload 需要包含 `user_id`、`role`、`exp`。
- 后端 `verify_admin` 改为校验登录用户存在、未禁用且 `role=admin`。

### 前端认证状态

前端从 `admin_token` 迁移为通用 `auth_token`：

- 登录后保存 token 和用户角色。
- 根据 `role=admin` 显示后台入口。
- 公开页如果用户未登录，点击 `AI 分析` 时进入登录或注册流程，登录后回到原页面。

## 区块级 AI 分析交互

公开页面每个内容方块标题右侧增加轻量 `AI 分析` 按钮。按钮使用统一图标和文字，不做高饱和大面积强调。

点击行为：

- 未登录：打开登录/注册入口，或跳转登录页并保留返回地址。
- 已登录且有有效缓存：打开抽屉并展示缓存结果，不调用模型。
- 已登录且无有效缓存：打开抽屉，展示 skeleton loading，并触发生成。
- 管理员可点击 `重新分析` 强制跳过缓存。
- 普通用户不能强制刷新仍有效的缓存。

桌面端使用右侧抽屉。移动端使用底部 Sheet。抽屉打开时不改变页面网格布局，不会把其他方块顶开。

### 抽屉内容

抽屉按信息层级展示：

- 顶部：方块名称、状态、模型名、生成时间。
- 核心总结：自适应 1-4 条，不强制一句话。
- 关键变化：0-3 条，有明显变化才展示。
- 风险/不确定性：0-2 条，没有则隐藏。
- 相关实体：0-8 个，股票、板块、公司、球队、模型等。
- 分析依据：默认折叠，只显示引用数量；展开后显示标题、来源、时间。
- 底部：token 消耗、是否估算、管理员的重新分析按钮。

### 动效与可用性

- 按钮 hover 和 press 使用轻微反馈。
- 抽屉进入使用 slide-in + fade，持续 150-250ms。
- 生成中使用 skeleton，不使用长时间大转圈。
- 结果区域可以轻微淡入，但不做装饰性动效。
- 尊重 `prefers-reduced-motion`。
- 按钮、关闭、重新分析等交互控件需要可键盘访问并有可见 focus。

## 后端数据模型

### users

新增 `users`：

- `id`
- `username`
- `email`
- `password_hash`
- `role`: `admin` / `user`
- `status`: `active` / `disabled`
- `last_login_at`
- `created_at`
- `updated_at`

约束：

- `username` 唯一。
- `email` 可选但如果填写需要唯一。
- 密码只存 hash，不存明文。首版使用 `bcrypt` 或同等级的慢哈希算法。
- 首版不做邮箱验证。

### ai_block_analyses

新增 `ai_block_analyses`：

- `id`
- `page_route`
- `block_id`
- `block_title`
- `source_type`
- `data_hash`
- `status`: `processing` / `generated` / `failed`
- `summary_points_json`
- `key_changes_json`
- `risk_points_json`
- `related_entities_json`
- `evidence_refs_json`
- `model_config_id`
- `generated_by_model`
- `generated_by_user_id`
- `token_usage_id`
- `error_message`
- `generated_at`
- `expires_at`
- `created_at`
- `updated_at`

缓存规则：

- 缓存键为 `page_route + block_id + data_hash`。
- `data_hash` 基于当前方块实际展示的数据生成，不基于方块配置生成。
- 有未过期 `generated` 记录时直接返回缓存。
- 缓存 TTL 首版为 60 分钟。
- 方块数据变化后 `data_hash` 变化，自然生成新分析。
- 管理员强制重新分析时跳过缓存，并新增记录，不覆盖旧记录。
- 建议索引：`page_route + block_id + data_hash + status + expires_at`。

### ai_token_usages

新增 `ai_token_usages`：

- `id`
- `user_id`
- `model_config_id`
- `model_name`
- `usage_type`: `block_analysis` / `topic_summary` / `item_enrichment`
- `prompt_tokens`
- `completion_tokens`
- `total_tokens`
- `estimated`
- `request_status`: `success` / `failed`
- `related_job_id`
- `related_block_analysis_id`
- `created_at`

记录规则：

- 只有真实调用模型时写入。
- 读取缓存不写 token 使用。
- 模型返回 usage 时使用真实 token。
- 模型没有返回 usage 时按字符数估算，并设置 `estimated=true`。
- 失败调用如果已有 token usage，也要记录；如果无法取得 usage，则记录 0 或估算值并标记失败。

### ai_generation_jobs 扩展

现有 `ai_generation_jobs` 继续保留，新增：

- `job_type=block_analysis`
- 可选关联 `block_analysis_id`
- 可选关联 `user_id`

`ai_generation_jobs` 负责任务日志，`ai_token_usages` 负责成本和用量统计。

## API 设计

### 认证 API

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`

登录返回：

- `token`
- `user.id`
- `user.username`
- `user.role`
- `user.status`

### 公开页 AI API

所有区块 AI 分析 API 都要求登录。

`GET /api/ai/block-analyses`

参数：

- `page_route`
- `block_id`

作用：

- 只读取有效缓存。
- 没有缓存时返回 404，不触发模型调用。

`POST /api/ai/block-analyses`

参数：

- `page_route`
- `block_id`

作用：

- 命中有效缓存时返回缓存。
- 无缓存或缓存过期时触发模型生成。
- 真实调用模型时写入 `ai_generation_jobs`、`ai_block_analyses` 和 `ai_token_usages`。

### 管理员 API

`POST /api/admin/ai/block-analyses/{id}/regenerate`

- 管理员强制重新生成。
- 跳过缓存。

`GET /api/admin/ai/token-usages`

- 管理员查看 token 使用记录。
- 支持按用户、模型、场景、时间范围筛选。

`GET /api/admin/users`

- 管理员查看用户列表和基础用量摘要。

`PATCH /api/admin/users/{id}`

- 首版只支持启用和禁用用户。

## Prompt 与输出结构

模型输出必须是 JSON：

```json
{
  "summary_points": ["根据内容复杂度输出 1-4 条"],
  "key_changes": ["0-3 条，有明显变化才输出"],
  "risk_points": ["0-2 条，不确定性或风险"],
  "related_entities": ["0-8 个股票、行业、球队、公司、模型等实体"],
  "confidence": 0.0
}
```

Prompt 约束：

- 只基于方块内提供的内容分析，不补充外部事实。
- 根据内容复杂度自适应总结数量。
- 如果多个内容都重要，输出 2-4 条核心总结。
- 不要为了凑数量输出空泛观点。
- 股票类不得输出买入、卖出、持有等确定性投资建议。
- 不得使用“必然”“确定”“一定上涨”“一定下跌”等绝对表达。
- 内容不足时返回较低 `confidence`，并说明信息不足。

服务端校验：

- `summary_points`: 1-4 条，每条最多 160 字。
- `key_changes`: 0-3 条，每条最多 140 字。
- `risk_points`: 0-2 条，每条最多 140 字。
- `related_entities`: 0-8 个，每个最多 40 字。
- `confidence`: 0-1。
- 类型错误或 JSON 无法解析时，生成失败并记录任务日志。
- 字段超长可以截断，但缺少核心字段应判失败。

## 错误与降级

- 未登录点击 AI 分析：显示登录/注册入口，不触发请求。
- 登录用户被禁用：返回 403，前端提示账号已禁用。
- 未配置默认模型：抽屉显示“管理员尚未配置 AI 模型”。
- 模型调用失败：抽屉展示失败状态和重试入口；普通用户重试会重新消耗一次真实调用。
- 命中缓存：不显示 loading，不扣 token。
- 内容不足：返回低置信度分析，不视为系统错误。

## 后台展示

新增或扩展后台页面：

- 用户管理：用户、角色、状态、注册时间、最近登录、启用/禁用。
- AI 用量：按用户、模型、场景和日期展示 token 使用。

首版统计以表格为主，不做复杂图表：

- 今日 token
- 本月 token
- 最近调用记录
- 估算 token 标记
- 失败调用标记

## 测试策略

后端测试：

- 注册、登录、`/api/auth/me`。
- 禁用用户无法登录和调用 AI。
- 管理员可以访问后台，普通用户不能访问后台。
- 区块分析命中缓存时不调用模型、不写 token usage。
- 无缓存时调用模型并写入分析、job、token usage。
- 模型返回 usage 时记录真实 token。
- 模型不返回 usage 时记录估算 token。
- Prompt 输出字段校验边界。
- 管理员强制重新分析跳过缓存。

前端测试：

- 未登录点击 `AI 分析` 出现登录入口。
- 已登录打开抽屉并显示缓存结果。
- 生成中显示 skeleton。
- 失败状态可读。
- 分析依据默认折叠，可展开。
- 普通用户不显示后台入口。
- 管理员显示后台入口和重新分析按钮。

手动验证：

- 在 `/topics/stocks`、`/topics/ai`、`/topics/football` 检查按钮和抽屉布局。
- 检查移动端底部 Sheet。
- 检查抽屉不会改变页面网格布局。
- 检查 token 用量在后台可见。

## 实施顺序

1. 新增用户表、认证服务和统一 auth API。
2. 将管理员校验迁移到用户角色模型，同时兼容现有管理员登录。
3. 新增区块分析表、token usage 表和相关迁移。
4. 新增区块分析服务：采集方块展示数据、生成 data hash、缓存判断、模型调用、token 记录。
5. 新增区块分析 API 和管理员 token usage API。
6. 前端迁移 auth context，支持普通用户和管理员角色。
7. 公开页增加 `AI 分析` 按钮和右侧抽屉。
8. 后台增加用户管理和 AI 用量表格。
9. 补充后端和前端测试。
