from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from apps.api.dependencies import get_engine, get_redis

router = APIRouter()


@router.get("/")
async def root() -> dict[str, str]:
    return {"service": "postupi-ai-api", "version": "0.1.0"}


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(
    engine: Annotated[AsyncEngine, Depends(get_engine)],
    redis: Annotated[Redis[str], Depends(get_redis)],
) -> dict[str, str]:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        await redis.ping()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="dependencies unavailable") from exc
    return {"status": "ok"}
