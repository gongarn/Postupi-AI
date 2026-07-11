from datetime import UTC, datetime


async def system_ping(_: object) -> dict[str, str]:
    return {"status": "ok", "timestamp": datetime.now(UTC).isoformat()}
