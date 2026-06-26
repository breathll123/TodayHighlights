from datetime import timezone, timedelta

from pydantic_settings import BaseSettings, SettingsConfigDict

SH_TZ = timezone(timedelta(hours=8))  # Asia/Shanghai UTC+8


class Settings(BaseSettings):
    database_url: str = "mysql+pymysql://daily:daily@127.0.0.1:3306/daily_highlights"
    app_secret_key: str
    cors_origins: str = "http://localhost:5173,http://localhost:5175,http://192.168.1.12:5175"
    scheduler_enabled: bool = True
    crawl_reconcile_on_startup: bool = True  # 启动时把遗留的 running 任务标记失败，释放运行守卫
    eastmoney_proxy: str | None = None  # e.g. http://127.0.0.1:7890
    redis_enabled: bool = False
    redis_url: str = "redis://127.0.0.1:6379/0"
    redis_key_prefix: str = "today-highlights"
    redis_socket_timeout_seconds: float = 1.0
    redis_lock_ttl_seconds: int = 45
    redis_retry_interval_seconds: int = 30
    artificial_analysis_api_key: str = ""
    artificial_analysis_api_base: str = "https://artificialanalysis.ai/api/v2"
    artificial_analysis_sync_enabled: bool = False
    artificial_analysis_quota_reserve: int = 2
    artificial_analysis_max_response_bytes: int = 10 * 1024 * 1024
    artificial_analysis_request_timeout_seconds: float = 30.0
    artificial_analysis_schedule_morning: str = "08:30"
    artificial_analysis_schedule_evening: str = "20:30"
    artificial_analysis_stale_hours: int = 36
    github_token: str = ""  # optional PAT — raises GitHub search rate limit 10→30/min
    github_skills_topics: str = ""
    github_skills_min_stars: int = 20
    github_skills_top_k: int = 100  # how many top-starred candidates to classify
    github_skills_classify_batch: int = 18
    log_dir: str = "logs"
    log_level: str = "INFO"
    log_rotation: str = "daily"
    log_retention_days: int = 14
    log_max_message_length: int = 4000
    log_console_enabled: bool = True
    log_slow_request_ms: int = 2000
    log_access_exclude_paths: str = ""
    log_trust_proxy_headers: bool = False
    log_queue_size: int = 10_000
    log_detail_crawler: bool = True
    log_detail_ai: bool = True
    log_response_preview_chars: int = 500
    log_url_query_mode: str = "safe"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
