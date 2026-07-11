from datetime import UTC, datetime

from arq import ArqRedis


async def system_ping(_: object) -> dict[str, str]:
    return {"status": "ok", "timestamp": datetime.now(UTC).isoformat()}


async def enqueue_itmo_refresh(ctx: dict[str, object]) -> None:
    await _enqueue(ctx, "ingest_snapshot_job", "itmo-refresh")


async def ingest_snapshot_job(
    ctx: dict[str, object], snapshot_id: str | None = None
) -> dict[str, str]:
    # Network fetching remains intentionally outside Stage 7.
    if snapshot_id:
        await _enqueue(ctx, "diff_snapshot_job", f"diff:{snapshot_id}", snapshot_id)
        return {"status": "queued", "snapshot": snapshot_id}
    return {"status": "skipped", "reason": "no_source_payload"}


async def diff_snapshot_job(
    ctx: dict[str, object], snapshot_id: str | None = None
) -> dict[str, str]:
    if snapshot_id:
        await _enqueue(ctx, "forecast_recompute_job", f"forecast:{snapshot_id}", snapshot_id)
        return {"status": "queued", "snapshot": snapshot_id}
    return {"status": "skipped", "snapshot": "none"}


async def forecast_recompute_job(
    ctx: dict[str, object], snapshot_id: str | None = None
) -> dict[str, str]:
    if snapshot_id:
        await _enqueue(ctx, "notify_users_job", f"notify:{snapshot_id}", snapshot_id)
        return {"status": "queued", "snapshot": snapshot_id}
    return {"status": "skipped", "snapshot": "none"}


async def notify_users_job(_: dict[str, object], snapshot_id: str | None = None) -> dict[str, str]:
    # Telegram delivery belongs to the bot process, which alone holds its token.
    return {"status": "skipped", "snapshot": snapshot_id or "none"}


async def _enqueue(
    ctx: dict[str, object], job_name: str, job_id: str, *args: str
) -> None:
    redis = ctx.get("redis")
    if not isinstance(redis, ArqRedis):
        return
    await redis.enqueue_job(job_name, *args, _job_id=job_id)
