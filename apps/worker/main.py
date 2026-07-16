from typing import cast

from arq.connections import RedisSettings
from arq.cron import cron
from redis.asyncio import Redis

from apps.worker.jobs import (
    diff_snapshot_job,
    enqueue_itmo_refresh,
    forecast_recompute_job,
    ingest_itmo_batch_job,
    ingest_snapshot_job,
    notify_users_job,
    system_ping,
)
from packages.common.config import get_settings


async def refresh_health(ctx: dict[str, object]) -> None:
    redis = cast(Redis, ctx["redis"])
    settings = get_settings()
    await redis.set(settings.worker_health_key, "ok", ex=settings.worker_health_max_age_seconds)


class WorkerSettings:
    functions = [
        system_ping,
        ingest_itmo_batch_job,
        ingest_snapshot_job,
        diff_snapshot_job,
        forecast_recompute_job,
        notify_users_job,
    ]
    cron_jobs = [cron(refresh_health, second={0}), cron(enqueue_itmo_refresh, minute={0})]
    health_check_interval = 10
    max_jobs = 5
    max_tries = 3
    keep_result = 0
    redis_settings = RedisSettings.from_dsn(str(get_settings().redis_url))

    @staticmethod
    async def on_startup(ctx: dict[str, object]) -> None:
        await refresh_health(ctx)

    @staticmethod
    async def on_shutdown(_: dict[str, object]) -> None:
        return None
