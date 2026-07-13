import asyncio
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from packages.common.config import get_settings, require_uid_hmac_secret
from packages.parsers.hse import HseParser
from packages.parsers.hse_client import HseClient
from packages.parsers.ingestion import IngestionOutcome, persist_snapshot
from packages.parsers.storage import DiscardingRawSnapshotStorage
from packages.persistence.uow import UnitOfWork


async def ingest_hse_pilot() -> IngestionOutcome:
    settings = get_settings()
    fresh = await HseClient().fetch_fresh_snapshot()
    parser = HseParser(
        uid_secret=require_uid_hmac_secret(settings),
        campaign_year=2026,
        competitive_group_id=fresh.selection["competitiveGroupId"],
        set_of_competitive_group_id=fresh.selection["setOfCompetitiveGroupId"],
        place_type=fresh.selection["placeType"],
        level=fresh.selection["level"],
        title=fresh.title,
        place_count=0,
        list_mode="registration",
    )
    result = parser.parse(
        fresh.applicants,
        source_url="https://pk.hse.ru/admissions/api/applicant",
        fetched_at=datetime.now(UTC),
    )
    if result.snapshot is None:
        return IngestionOutcome(result.status, None, 0, 0, result.errors)
    engine = create_async_engine(str(settings.database_url), pool_pre_ping=True)
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with UnitOfWork(factory) as uow:
            return await persist_snapshot(
                uow,
                result.snapshot,
                raw_storage=DiscardingRawSnapshotStorage(),
                raw_content=fresh.applicants,
                content_type="application/json",
            )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(ingest_hse_pilot())
