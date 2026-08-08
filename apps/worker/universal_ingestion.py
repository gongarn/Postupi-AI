from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, cast

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker

from packages.common.config import Settings, get_settings, require_uid_hmac_secret
from packages.common.runtime import create_engine
from packages.parsers.base import BaseUniversityParser, ParserResultStatus
from packages.parsers.ingestion import IngestionOutcome, persist_snapshot
from packages.parsers.registry import SOURCES, UniversitySource
from packages.parsers.storage import DiscardingRawSnapshotStorage
from packages.persistence.uow import UnitOfWork


async def ingest_all_universities() -> dict[str, list[IngestionOutcome]]:
    """Загружает все активные вузы из реестра (кроме ИТМО/ВШЭ/МФТИ —
    у них собственные ингейшены со специфичной семантикой batch)."""
    settings = get_settings()
    engine = create_engine(str(settings.database_url))
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            results: dict[str, list[IngestionOutcome]] = {}
            for code in _new_university_codes(settings):
                source = SOURCES.get(code)
                if source is None or not source.enabled:
                    continue
                try:
                    async with UnitOfWork(factory) as uow:
                        outcomes = await _ingest_source(uow, source, settings, client)
                        results[code] = outcomes
                except Exception as exc:  # noqa: BLE001 — один вуз не должен ронять цикл
                    results[code] = [
                        IngestionOutcome(ParserResultStatus.FAILED, None, 0, 0, (str(exc),))
                    ]
        return results
    finally:
        await engine.dispose()


async def _ingest_source(
    uow: UnitOfWork,
    source: UniversitySource,
    settings: Settings,
    client: httpx.AsyncClient,
) -> list[IngestionOutcome]:
    uid_secret = require_uid_hmac_secret(settings)
    documents = await source.fetcher(client)
    outcomes: list[IngestionOutcome] = []
    for document in documents:
        metadata = document.metadata or {}
        parser = _build_parser(source, uid_secret, metadata)
        result = parser.parse(
            document.content,
            source_url=document.source_url,
            fetched_at=datetime.now(UTC),
        )
        if result.snapshot is None:
            outcomes.append(IngestionOutcome(result.status, None, 0, 0, result.errors))
            continue
        parsed = result.snapshot
        raw_payload = {
            **parsed.raw_payload,
            "source": source.code,
            "fetched_at": parsed.fetched_at.isoformat(),
        }
        outcomes.append(
            await persist_snapshot(
                uow,
                replace(parsed, raw_payload=raw_payload),
                raw_storage=DiscardingRawSnapshotStorage(),
                raw_content=document.content,
                content_type=document.content_type,
            )
        )
    return outcomes


def _build_parser(
    source: UniversitySource, uid_secret: str, metadata: dict[str, str | int | None]
) -> BaseUniversityParser:
    return _build_parser_any(source, uid_secret, metadata)


def _build_parser_any(
    source: UniversitySource, uid_secret: str, metadata: dict[str, str | int | None]
) -> BaseUniversityParser:
    kwargs: dict[str, object] = {"uid_secret": uid_secret, "campaign_year": 2026}
    if "group_id" in metadata:
        kwargs["group_id"] = metadata["group_id"]
    if "title" in metadata:
        kwargs["title"] = metadata["title"]
    if "financing" in metadata:
        kwargs["financing"] = metadata["financing"]
    if "faculty_code" in metadata:
        kwargs["faculty_code"] = metadata["faculty_code"]
    if "section_anchor" in metadata:
        from packages.parsers.msu import MsuSection

        kwargs["section"] = MsuSection(
            anchor_id=str(metadata["section_anchor"]),
            program=str(metadata.get("section_program") or "unknown"),
            condition=str(metadata.get("section_condition") or "general_competition"),
            seat_count=(
                int(cast(int, metadata["section_seat"]))
                if isinstance(metadata.get("section_seat"), int)
                else None
            ),
            html="",
        )
    parser_type = cast(Any, source.parser)
    return cast(BaseUniversityParser, parser_type(**kwargs))


def _new_university_codes(settings: Settings) -> list[str]:
    from packages.common.config import active_university_codes

    return [
        code
        for code in active_university_codes(settings)
        if code not in {"itmo", "hse", "mipt"}
    ]
