# 每日看点 Daily Highlights

Daily Highlights 是一个 Python + React MVP，用于采集雪球股票内容、生成 AI 摘要并审核每日阅读页面的看点。

## 后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[test]"
alembic upgrade head
uvicorn app.main:app --reload
```

## 前端

```bash
cd frontend
npm install
npm run dev
```

## 所需环境变量

复制 `.env.example` 为 `backend/.env` 并设置：

- `DATABASE_URL` - MySQL 数据库连接字符串
- `APP_SECRET_KEY` - Fernet 加密密钥
- `CORS_ORIGINS` - 前端地址
- `SCHEDULER_ENABLED` - 是否启用定时爬取

使用以下命令生成 Fernet 密钥：

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## MVP 范围

- 雪球数据源适配器，支持手动 Cookie 配置。
- MySQL 持久化。
- 手动和定时爬取。
- OpenAI 兼容的 AI 摘要。
- 公开摘要和股票页面。
- 管理后台数据源、任务、看点和模型设置页面。

本系统不实现自动登录、验证码破解或反爬虫绕过。
