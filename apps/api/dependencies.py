from collections.abc import AsyncIterator

from fastapi import Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine


def get_engine(request: Request) -> AsyncEngine:
    return request.app.state.engine


def get_redis(request: Request) -> Redis[str]:
    return request.app.state.redis


async def close_runtime(engine: AsyncEngine, redis: Redis[str]) -> AsyncIterator[None]:
    try:
        yield
    finally:
        await redis.aclose()
        await engine.dispose()
