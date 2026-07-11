from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.diff import diff_snapshots
from packages.persistence.models import Application, ApplicationEvent, ListSnapshot
from packages.persistence.uow import UnitOfWork
from tests.integration.test_persistence import _seed_group


async def _snapshot(session: AsyncSession, group_id, suffix: str) -> ListSnapshot:
    value = ListSnapshot(
        competition_group_id=group_id,
        campaign_year=2025,
        source_url="https://example.invalid/itmo",
        content_hash=suffix * 64,
        fetched_at=datetime.now(UTC),
        parser_version="test",
        status="valid",
        row_count=0,
        raw_storage_key=f"raw/{suffix}",
        raw_payload={},
    )
    session.add(value)
    await session.flush()
    return value


def _application(
    snapshot: ListSnapshot,
    uid: str,
    *,
    condition: str = "general_competition",
    **changes: object,
) -> Application:
    payload = {
        "is_have_advantages": False,
        "main_top_priority": False,
        "highest_passageway_priority": False,
    }
    payload.update(changes.pop("payload", {}))
    values: dict[str, object] = {
        "snapshot_id": snapshot.id,
        "competition_group_id": snapshot.competition_group_id,
        "identity_namespace": "test:2025",
        "applicant_uid_hmac": uid,
        "admission_condition": condition,
        "rank": 1,
        "enrollment_priority": 1,
        "consent": False,
        "competitive_score": 200,
        "application_status": "pending",
        "raw_payload": payload,
    }
    values.update(changes)
    return Application(**values)


@pytest.mark.asyncio
async def test_diff_events_and_idempotent_retry(db_session: AsyncSession) -> None:
    _, group = await _seed_group(db_session)
    previous = await _snapshot(db_session, group.id, "a")
    current = await _snapshot(db_session, group.id, "b")
    db_session.add_all(
        [
            _application(previous, "uid-old"),
            _application(previous, "uid-change"),
            _application(previous, "uid-condition"),
            _application(previous, "uid-bvi", payload={"bvi": False}),
            _application(current, "uid-new"),
            _application(
                current,
                "uid-change",
                rank=2,
                competitive_score=201,
                enrollment_priority=2,
                consent=True,
                application_status="recommended",
                payload={"is_have_advantages": True},
            ),
            _application(current, "uid-condition", condition="by_special_quota"),
            _application(current, "uid-bvi", payload={"bvi": True}),
        ]
    )
    await db_session.flush()
    uow = UnitOfWork(lambda: db_session)
    uow.session = db_session
    first = await diff_snapshots(
        uow, previous_snapshot_id=previous.id, current_snapshot_id=current.id
    )
    second = await diff_snapshots(
        uow, previous_snapshot_id=previous.id, current_snapshot_id=current.id
    )
    await db_session.commit()
    assert first.event_counts["appeared"] == 1
    assert first.event_counts["disappeared"] == 1
    assert first.event_counts["condition_changed"] == 1
    assert first.event_counts["rank_changed"] == 1
    assert first.event_counts["score_changed"] == 1
    assert first.event_counts["priority_changed"] == 1
    assert first.event_counts["consent_changed"] == 1
    assert first.event_counts["status_changed"] == 1
    assert first.event_counts["advantages_changed"] == 1
    assert first.event_counts["bvi_changed"] == 1
    assert second.event_counts == {}
    events = list(
        (
            await db_session.scalars(
                select(ApplicationEvent).where(
                    ApplicationEvent.previous_snapshot_id == previous.id,
                    ApplicationEvent.current_snapshot_id == current.id,
                )
            )
        ).all()
    )
    assert len(events) == 10
    assert all("raw_payload" not in event.before_json for event in events)


@pytest.mark.asyncio
async def test_diff_rejects_incompatible_snapshots(db_session: AsyncSession) -> None:
    _, group = await _seed_group(db_session)
    previous = await _snapshot(db_session, group.id, "c")
    current = await _snapshot(db_session, group.id, "d")
    current.campaign_year = 2026
    uow = UnitOfWork(lambda: db_session)
    uow.session = db_session
    with pytest.raises(ValueError, match="campaigns differ"):
        await diff_snapshots(uow, previous_snapshot_id=previous.id, current_snapshot_id=current.id)
