from typing import cast

from arq.connections import RedisSettings
from arq.cron import cron
from redis.asyncio import Redis

from apps.worker.jobs import system_ping
from packages.common.config import get_settings


async def refresh_health(ctx: dict[str, object]) -> None:
    redis = cast(Redis, ctx["redis"])
    settings = get_settings()
    await redis.set(settings.worker_health_key, "ok", ex=settings.worker_health_max_age_seconds)


class WorkerSettings:
    functions = [system_ping]
    cron_jobs = [cron(refresh_health, second={0})]
    health_check_interval = 10
    max_jobs = 5
    keep_result = 0
    redis_settings = RedisSettings.from_dsn(str(get_settings().redis_url))

    @staticmethod
    async def on_startup(ctx: dict[str, object]) -> None:
        await refresh_health(ctx)

    @staticmethod
    async def on_shutdown(_: dict[str, object]) -> None:
        return None
