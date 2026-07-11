from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from packages.persistence.models import (
    Application,
    CompetitionGroup,
    ForecastRun,
    ListSnapshot,
    Notification,
    TrackedUser,
    University,
    UserTarget,
)


async def _seed_group(session: AsyncSession) -> tuple[University, CompetitionGroup]:
    university = University(
        code=f"test-{uuid4().hex[:12]}", name="Test University", parser_status="active"
    )
    session.add(university)
    await session.flush()
    group = CompetitionGroup(
        university_id=university.id,
        campaign_year=2025,
        external_group_id="test-group",
        title="Test Group",
        identity_namespace="test:2025",
        priority_kind="unknown",
        priority_confidence="unknown",
    )
    session.add(group)
    await session.flush()
    return university, group


@pytest.mark.asyncio
async def test_migration_has_expected_tables(db_engine: AsyncEngine) -> None:
    async with db_engine.connect() as connection:
        names = await connection.run_sync(lambda conn: inspect(conn).get_table_names())
    assert {
        "universities",
        "competition_groups",
        "list_snapshots",
        "applications",
        "application_events",
        "tracked_users",
        "user_targets",
        "forecast_runs",
        "notifications",
    } <= set(names)


@pytest.mark.asyncio
async def test_schema_has_no_raw_uid_column(db_engine: AsyncEngine) -> None:
    async with db_engine.connect() as connection:
        columns = await connection.run_sync(lambda conn: inspect(conn).get_columns("applications"))
    names = {column["name"] for column in columns}
    assert "applicant_uid" not in names
    assert "applicant_uid_hmac" in names


@pytest.mark.asyncio
async def test_snapshot_deduplication_and_application_namespace(db_session: AsyncSession) -> None:
    _, group = await _seed_group(db_session)
    snapshot = ListSnapshot(
        competition_group_id=group.id,
        campaign_year=2025,
        source_url="https://example.invalid/list",
        content_hash="a" * 64,
        fetched_at=datetime.now(UTC),
        parser_version="test-1",
        status="valid",
        row_count=1,
        raw_storage_key="raw/test",
        raw_payload={"rank": 1},
    )
    db_session.add(snapshot)
    await db_session.flush()
    db_session.add(
        Application(
            snapshot_id=snapshot.id,
            competition_group_id=group.id,
            identity_namespace="test:2025",
            applicant_uid_hmac="b" * 64,
            admission_condition="general_competition",
            rank=1,
            raw_payload={"rank": 1},
        )
    )
    await db_session.commit()
    duplicate = ListSnapshot(
        competition_group_id=group.id,
        campaign_year=2025,
        source_url="https://example.invalid/list",
        content_hash="a" * 64,
        fetched_at=datetime.now(UTC),
        parser_version="test-1",
        status="valid",
        row_count=1,
        raw_storage_key="raw/test-2",
        raw_payload={},
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_application_requires_identity_namespace(db_session: AsyncSession) -> None:
    _, group = await _seed_group(db_session)
    snapshot = ListSnapshot(
        competition_group_id=group.id,
        campaign_year=2025,
        source_url="https://example.invalid/list/no-namespace",
        content_hash="e" * 64,
        fetched_at=datetime.now(UTC),
        parser_version="test-1",
        status="valid",
        row_count=1,
        raw_storage_key="raw/no-namespace",
        raw_payload={},
    )
    db_session.add(snapshot)
    await db_session.flush()
    db_session.add(
        Application(
            snapshot_id=snapshot.id,
            competition_group_id=group.id,
            identity_namespace=None,
            applicant_uid_hmac="f" * 64,
            admission_condition="general_competition",
            rank=1,
            raw_payload={},
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_user_delete_cascades_only_user_owned_rows(db_session: AsyncSession) -> None:
    _, group = await _seed_group(db_session)
    snapshot = ListSnapshot(
        competition_group_id=group.id,
        campaign_year=2025,
        source_url="https://example.invalid/list",
        content_hash="c" * 64,
        fetched_at=datetime.now(UTC),
        parser_version="test-1",
        status="valid",
        row_count=1,
        raw_storage_key="raw/test",
        raw_payload={},
    )
    user = TrackedUser(telegram_user_id=1001, policy_version="v1", consented_at=datetime.now(UTC))
    db_session.add_all([snapshot, user])
    await db_session.flush()
    target = UserTarget(
        tracked_user_id=user.id,
        competition_group_id=group.id,
        identity_namespace="test:2025",
        applicant_uid_hmac="d" * 64,
    )
    db_session.add(target)
    await db_session.flush()
    db_session.add_all(
        [
            ForecastRun(
                tracked_user_id=user.id,
                user_target_id=target.id,
                probability_low=0.1,
                probability_high=0.5,
                confidence="unknown",
                explanation={},
            ),
            Notification(
                tracked_user_id=user.id,
                user_target_id=target.id,
                kind="test",
                payload={},
                delivery_status="pending",
            ),
        ]
    )
    await db_session.commit()
    await db_session.delete(user)
    await db_session.commit()
    assert await db_session.scalar(select(TrackedUser).where(TrackedUser.id == user.id)) is None
    assert (
        await db_session.scalar(select(ListSnapshot).where(ListSnapshot.id == snapshot.id))
        is not None
    )
    assert await db_session.scalar(select(UserTarget).where(UserTarget.id == target.id)) is None
    assert (
        await db_session.scalar(select(ForecastRun).where(ForecastRun.tracked_user_id == user.id))
        is None
    )
    assert (
        await db_session.scalar(select(Notification).where(Notification.tracked_user_id == user.id))
        is None
    )
