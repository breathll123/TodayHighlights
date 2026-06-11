from datetime import timezone, timedelta

from pydantic_settings import BaseSettings, SettingsConfigDict

SH_TZ = timezone(timedelta(hours=8))  # Asia/Shanghai UTC+8


class Settings(BaseSettings):
    database_url: str = "mysql+pymysql://daily:daily@127.0.0.1:3306/daily_highlights"
    app_secret_key: str
    cors_origins: str = "http://localhost:5173,http://localhost:5175,http://192.168.1.11:5175"
    scheduler_enabled: bool = True
    eastmoney_proxy: str | None = None  # e.g. http://127.0.0.1:7890
    redis_enabled: bool = False
    redis_url: str = "redis://127.0.0.1:6379/0"
    redis_key_prefix: str = "today-highlights"
    redis_socket_timeout_seconds: float = 1.0
    redis_lock_ttl_seconds: int = 45
    redis_retry_interval_seconds: int = 30

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
