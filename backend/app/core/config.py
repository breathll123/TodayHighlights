from datetime import timezone, timedelta

from pydantic_settings import BaseSettings, SettingsConfigDict

SH_TZ = timezone(timedelta(hours=8))  # Asia/Shanghai UTC+8


class Settings(BaseSettings):
    database_url: str = "mysql+pymysql://daily:daily@127.0.0.1:3306/daily_highlights"
    app_secret_key: str
    cors_origins: str = "http://localhost:5173"
    scheduler_enabled: bool = True
    eastmoney_proxy: str | None = None  # e.g. http://127.0.0.1:7890

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
