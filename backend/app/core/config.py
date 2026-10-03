from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Learning Platform API"
    database_url: str = (
        "postgresql+psycopg://learning:local-development-only@127.0.0.1:5433/learning_platform"
    )
    redis_cache_url: str = "redis://127.0.0.1:6379/0"
    redis_queue_url: str = "redis://127.0.0.1:6379/1"
    queue_name: str = "learning-platform"
    jwt_secret: SecretStr = Field(min_length=32)
    jwt_issuer: str = "learning-platform"
    jwt_audience: str = "learning-platform-api"
    access_token_minutes: int = Field(default=30, ge=1, le=1440)
    trial_days: int = Field(default=14, ge=1, le=365)
    cache_seconds: int = Field(default=60, ge=1, le=3600)
    expiration_interval_seconds: int = Field(default=60, ge=10)
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
