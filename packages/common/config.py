from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POSTUPI_", env_file=".env", extra="ignore")

    environment: str = Field(default="local", pattern=r"^(local|test|staging|production)$")
    log_level: str = Field(default="INFO", pattern=r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    database_url: str = "postgresql+asyncpg://postupi:postupi@localhost:5432/postupi"
    redis_url: str = "redis://localhost:6379/0"
    telegram_bot_token: SecretStr | None = None
    cross_university_matching_enabled: bool = False
    forecasting_enabled: bool = False
    worker_health_key: str = "postupi:worker:health"
    worker_health_max_age_seconds: int = Field(default=60, ge=5, le=3600)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
