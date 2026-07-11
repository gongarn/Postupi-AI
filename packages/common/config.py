from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POSTUPI_", env_file=".env", extra="ignore")

    environment: str = Field(default="local", pattern=r"^(local|test|staging|production)$")
    log_level: str = Field(default="INFO", pattern=r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    database_url: str = "postgresql+asyncpg://postupi:postupi@localhost:5432/postupi"
    redis_url: str = "redis://localhost:6379/0"
    uid_hmac_secret: SecretStr | None = None
    telegram_bot_token: SecretStr | None = None
    cross_university_matching_enabled: bool = False
    forecasting_enabled: bool = False
    worker_health_key: str = "postupi:worker:health"
    worker_health_max_age_seconds: int = Field(default=60, ge=5, le=3600)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def require_uid_hmac_secret(settings: Settings) -> str:
    if settings.uid_hmac_secret is None:
        raise ValueError("POSTUPI_UID_HMAC_SECRET is required for data access")
    value = settings.uid_hmac_secret.get_secret_value()
    if not value:
        raise ValueError("POSTUPI_UID_HMAC_SECRET must not be empty")
    return value
