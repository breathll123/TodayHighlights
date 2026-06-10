# 首次界面注册管理员设计

## 目标

移除公开的默认管理员密码和应用启动时自动创建管理员的行为。新部署通过数据库初始化脚本完成迁移，随后由用户在首次打开登录页时创建首个管理员。首个管理员创建完成后，公开注册永久关闭。

## 安全边界

- 仓库中不保存默认管理员密码。
- 应用启动不创建表、不创建用户、不写入管理员密码设置。
- 首次管理员注册仅在数据库中不存在有效管理员时开放。
- 首个管理员创建必须在单个数据库事务内完成，并通过唯一初始化标记避免并发创建多个管理员。
- 普通 `/api/auth/register` 接口关闭，不允许匿名用户继续注册普通账号。
- 管理员与普通用户统一通过 `/api/auth/login` 登录。
- 旧的 `/api/admin/login` 和 `app_settings.admin.password` 认证路径移除。

## 后端接口

### `GET /api/auth/setup-status`

无需认证，返回：

```json
{
  "setup_required": true
}
```

满足任一条件时返回 `false`：

- 存在 `system.admin_bootstrap_completed` 标记。
- 至少存在一个 `role=admin` 且 `status=active` 的非遗留管理员。

仅在没有完成标记、也没有有效非遗留管理员时返回 `true`。

该接口不返回用户名、邮箱、用户数量或其他可用于枚举账号的信息。

### `POST /api/auth/bootstrap-admin`

仅当 `setup_required=true` 时开放。请求字段沿用现有注册字段：

```json
{
  "username": "admin",
  "email": "admin@example.com",
  "password": "用户输入的密码"
}
```

行为：

1. 在事务中写入唯一键 `system.admin_bootstrap_completed` 作为初始化声明。
2. 再次检查是否已有有效管理员。
3. 创建首个 `role=admin`、`status=active` 用户。
4. 立即签发正常用户 Token 并返回 `AuthResponse`。
5. 后续调用返回 HTTP `409`，错误信息为 `Administrator already initialized`。

初始化标记存入主键唯一的 `app_settings.key`。标记写入和管理员创建处于同一事务：并发请求只有一个可以成功写入，失败请求捕获唯一约束冲突并返回 `409`；创建管理员失败时整个事务回滚，标记不会残留。该机制同时适用于 MySQL 和 SQLite 测试环境。

### `POST /api/auth/register`

移除公开注册路由。已有调用应得到 HTTP `404`。本次不实现管理员后台创建普通用户，该能力后续单独设计。

### `POST /api/admin/login`

移除旧路由。登录统一使用 `/api/auth/login`，用户名默认为 `admin` 的前端便利行为也一并移除，要求用户明确输入用户名或邮箱。

## 遗留默认管理员处理

历史版本可能存在自动创建的 `admin/admin123` 账号，以及 `app_settings` 中的 `admin.password`。

系统将同时满足以下条件的账号识别为遗留默认管理员：

- `username == "admin"`
- `role == "admin"`
- 当前密码哈希可由 `admin123` 验证
- `app_settings.admin.password` 不存在或值为 `admin123`

该账号不计入 `setup-status` 的有效管理员数量。首次管理员注册时：

- 如果用户选择用户名 `admin`，在原记录上重置用户名、邮箱、密码、角色和状态，保留用户 ID，避免外键断裂。
- 如果用户选择其他用户名，先将遗留账号设置为 `disabled` 并重命名为不会冲突的内部名称，再创建新管理员。
- 删除 `app_settings.admin.password` 遗留值。
- 成功提交 `system.admin_bootstrap_completed` 标记，之后即使管理员被禁用，公开初始化也不会重新开放。

任何已修改密码的管理员、非默认用户名管理员或其他有效管理员都不会被自动修改。

## 数据库初始化脚本

新增 `backend/scripts/init_db.py`，职责保持单一：

1. 校验当前目录和环境变量配置。
2. 执行 `alembic upgrade head`。
3. 检查现有管理员状态：已有非遗留管理员时补写完成标记；只有遗留 `admin/admin123` 时保持首次注册开放。
4. 删除不再使用的 `app_settings.admin.password` 遗留值。
5. 输出下一步提示：启动后端并在浏览器完成首个管理员注册。

脚本不接收、生成或保存任何密码，也不启动应用。

应用启动时删除 `Base.metadata.create_all()` 和所有种子逻辑。新增 Alembic 迁移以幂等方式创建默认 `stocks` 主题，应用启动不再静默写库。

## 前端流程

登录页加载时请求 `setup-status`：

- `setup_required=true`：显示“创建管理员”表单，包含用户名、可选邮箱、密码和确认密码。
- `setup_required=false`：显示现有登录表单。
- 状态请求失败：显示可重试错误，不猜测当前模式，也不开放管理员创建。

创建成功后复用现有 `AuthProvider` 持久化 Token 和用户信息，并跳转到首页。登录表单不再提供“注册”切换入口。

## 错误处理

- 两次密码不一致：前端阻止提交。
- 用户名为空或密码不满足现有 Schema：返回 `422`。
- 管理员已存在：返回 `409`，前端刷新状态并切换到登录页。
- 数据库未迁移或不可用：初始化脚本以非零状态退出；应用接口返回服务错误，不自动建表掩盖问题。
- 遗留账号识别失败：不修改账号；若其仍是有效管理员，则关闭首次注册。

## 测试

后端测试覆盖：

- 空数据库需要初始化。
- 首次注册创建管理员并返回 Token。
- 创建后 `setup_required=false`。
- 第二次初始化返回 `409`。
- 普通注册路由不可用。
- 应用启动不会自动创建管理员。
- 遗留 `admin/admin123` 不阻止首次初始化。
- 遗留账号原地重置或禁用后新建。
- 已修改密码的真实管理员不会被识别为遗留账号。

前端测试覆盖：

- 首次状态显示管理员创建表单。
- 已初始化状态显示登录表单且无公开注册链接。
- 创建管理员成功后持久化认证状态。
- 状态请求失败时不显示创建表单。
- 并发冲突 `409` 后切换到登录模式。

验证命令：

```bash
cd backend
APP_SECRET_KEY=<valid-fernet-key> python -m pytest tests -q

cd frontend
npm test
npm run build
```

## README 更新

快速开始顺序调整为：

1. 创建并配置 `backend/.env`。
2. 安装后端依赖。
3. 运行 `python scripts/init_db.py`。
4. 启动 FastAPI。
5. 启动前端。
6. 首次访问登录页并创建管理员。

README 明确说明没有默认密码，首次管理员创建后公开注册即关闭。
