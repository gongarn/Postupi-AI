import pytest

from packages.common.config import Settings


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        environment="test",
        database_url="postgresql+asyncpg://postupi:postupi@localhost:5432/postupi",
        redis_url="redis://localhost:6379/0",
    )
