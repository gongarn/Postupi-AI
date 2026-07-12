from __future__ import annotations

from dataclasses import dataclass

from packages.parsers.base import ParsedSnapshot, ParserResultStatus
from packages.parsers.storage import RawSnapshotMetadata, RawSnapshotStorage
from packages.persistence.models import Application
from packages.persistence.uow import UnitOfWork


@dataclass(frozen=True)
class IngestionOutcome:
    status: ParserResultStatus
    snapshot_id: str | None
    application_count: int
    unique_uid_count: int
    errors: tuple[str, ...] = ()


async def persist_snapshot(
    uow: UnitOfWork,
    parsed: ParsedSnapshot,
    *,
    raw_storage: RawSnapshotStorage,
    raw_content: bytes,
    content_type: str = "text/html",
) -> IngestionOutcome:
    raw_key = raw_storage.put(
        raw_content,
        metadata=RawSnapshotMetadata(
            source_url=parsed.source_url,
            fetched_at=parsed.fetched_at.isoformat(),
            content_type=content_type,
            content_hash=parsed.content_hash,
            parser_version=parsed.parser_version,
        ),
    )
    university = await uow.universities.get_by_code(parsed.group.university_code)
    if university is None:
        university = await uow.universities.add(
            code=parsed.group.university_code,
            name=parsed.group.university_name,
            parser_key=parsed.group.university_code,
        )
    group = await uow.competition_groups.get_by_external_key(
        university_id=university.id,
        campaign_year=parsed.group.campaign_year,
        external_group_id=parsed.group.external_group_id,
    )
    if group is None:
        group = await uow.competition_groups.add(
            university_id=university.id,
            campaign_year=parsed.group.campaign_year,
            external_group_id=parsed.group.external_group_id,
            title=parsed.group.title,
            identity_namespace=parsed.group.identity_namespace,
            priority_kind=parsed.group.priority_kind,
            priority_confidence=parsed.group.priority_confidence,
        )
    existing = await uow.snapshots.get_by_content(
        competition_group_id=group.id,
        source_url=parsed.source_url,
        content_hash=parsed.content_hash,
    )
    if existing is not None:
        return IngestionOutcome(
            ParserResultStatus.VALID,
            str(existing.id),
            existing.row_count,
            len({application.applicant_uid_hmac for application in parsed.applications}),
        )
    snapshot = await uow.snapshots.add(
        competition_group_id=group.id,
        campaign_year=parsed.group.campaign_year,
        source_url=parsed.source_url,
        content_hash=parsed.content_hash,
        fetched_at=parsed.fetched_at,
        parser_version=parsed.parser_version,
        status=ParserResultStatus.VALID,
        row_count=len(parsed.applications),
        raw_storage_key=raw_key,
        raw_payload=parsed.raw_payload,
    )
    for item in parsed.applications:
        uow.session.add(
            Application(
                snapshot_id=snapshot.id,
                competition_group_id=group.id,
                identity_namespace=item.identity_namespace,
                applicant_uid_hmac=item.applicant_uid_hmac,
                admission_condition=item.admission_condition,
                rank=item.rank,
                enrollment_priority=item.enrollment_priority,
                competitive_score=item.competitive_score,
                application_status=item.application_status,
                consent=item.consent,
                raw_payload=item.raw_payload,
            )
        )
    await uow.session.flush()
    return IngestionOutcome(
        ParserResultStatus.VALID,
        str(snapshot.id),
        len(parsed.applications),
        len({application.applicant_uid_hmac for application in parsed.applications}),
    )
