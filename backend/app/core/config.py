from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "mysql+pymysql://daily:daily@127.0.0.1:3306/daily_highlights"
    app_secret_key: str
    cors_origins: str = "http://localhost:5173"
    scheduler_enabled: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
