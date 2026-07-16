from __future__ import annotations

import asyncio
import re
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker

from packages.common.config import get_settings, require_uid_hmac_secret
from packages.common.runtime import create_engine
from packages.parsers.ingestion import IngestionOutcome, persist_snapshot
from packages.parsers.itmo import ItmoParser
from packages.parsers.storage import DiscardingRawSnapshotStorage
from packages.persistence.uow import UnitOfWork

INDEX_URL = "https://abit.itmo.ru/ratings/bachelor"
GROUP_URL = "https://abit.itmo.ru/rating/bachelor/budget/{group_id}"


async def ingest_itmo_batch() -> list[IngestionOutcome]:
    settings = get_settings()
    batch_id = str(uuid4())
    async with httpx.AsyncClient(timeout=30) as client:
        group_ids = await _group_ids(client)
        responses = await asyncio.gather(
            *(_fetch_group(client, group_id) for group_id in group_ids)
        )
    contents = [
        (group_id, response) for group_id, response in zip(group_ids, responses, strict=True)
    ]
    if any(response.status_code != 200 for _, response in contents):
        raise RuntimeError("ITMO batch is incomplete")

    engine = create_engine(str(settings.database_url))
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        outcomes: list[IngestionOutcome] = []
        async with UnitOfWork(factory) as uow:
            for group_id, response in contents:
                result = ItmoParser(
                    uid_secret=require_uid_hmac_secret(settings), competitive_group_id=group_id
                ).parse(
                    response.content,
                    source_url=str(response.url),
                    fetched_at=datetime.now(UTC),
                )
                if result.snapshot is None:
                    outcomes.append(IngestionOutcome(result.status, None, 0, 0, result.errors))
                    continue
                parsed = result.snapshot
                raw_payload = {
                    **parsed.raw_payload,
                    "ingestion_batch": {"id": batch_id, "expected_group_count": len(group_ids)},
                }
                outcomes.append(
                    await persist_snapshot(
                        uow,
                        replace(parsed, raw_payload=raw_payload),
                        raw_storage=DiscardingRawSnapshotStorage(),
                        raw_content=response.content,
                    )
                )
        return outcomes
    finally:
        await engine.dispose()


async def _group_ids(client: httpx.AsyncClient) -> list[str]:
    response = await client.get(INDEX_URL)
    response.raise_for_status()
    group_ids = sorted(set(re.findall(r"/rating/bachelor/budget/(\d+)", response.text)))
    if not group_ids:
        raise RuntimeError("ITMO group index is empty")
    return group_ids


async def _fetch_group(client: httpx.AsyncClient, group_id: str) -> httpx.Response:
    return await client.get(GROUP_URL.format(group_id=group_id))


if __name__ == "__main__":
    asyncio.run(ingest_itmo_batch())
