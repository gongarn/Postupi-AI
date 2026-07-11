from typing import cast

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url, pool_pre_ping=True)


def create_redis(redis_url: str) -> Redis:
    return cast(Redis, Redis.from_url(redis_url, decode_responses=True))
