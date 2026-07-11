import asyncio
import sys

from redis.asyncio import Redis

from packages.common.config import get_settings


async def main() -> int:
    settings = get_settings()
    redis: Redis[str] = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        value = await redis.get(settings.worker_health_key)
        return 0 if value == "ok" else 1
    finally:
        await redis.aclose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
