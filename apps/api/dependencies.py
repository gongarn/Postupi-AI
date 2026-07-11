from collections.abc import AsyncIterator
from typing import cast

from fastapi import Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine


def get_engine(request: Request) -> AsyncEngine:
    return cast(AsyncEngine, request.app.state.engine)


def get_redis(request: Request) -> Redis:
    return cast(Redis, request.app.state.redis)


async def close_runtime(engine: AsyncEngine, redis: Redis) -> AsyncIterator[None]:
    try:
        yield
    finally:
        await redis.aclose()
        await engine.dispose()
