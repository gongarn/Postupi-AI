from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.forecasting.engine import AdmissionProbabilityEngine
from packages.forecasting.persistence import persist_forecast
from packages.forecasting.recompute import _candidate_cohorts, recompute_probabilistic_forecasts
from packages.persistence.models import (
    Application,
    ForecastRun,
    ListSnapshot,
    TrackedUser,
    University,
    UserTarget,
)
from packages.persistence.repositories import CompetitionGroupRepository
from packages.persistence.uow import UnitOfWork
from tests.unit.forecasting.test_engine import _input


@pytest.mark.asyncio
async def test_forecast_persistence_is_idempotent(db_session: AsyncSession) -> None:
    from tests.integration.test_persistence import _seed_group

    _, group = await _seed_group(db_session)
    snapshot = ListSnapshot(
        competition_group_id=group.id,
        campaign_year=2025,
        source_url="https://example.invalid/forecast",
        content_hash="9" * 64,
        fetched_at=datetime.now(UTC),
        parser_version="test",
        status="valid",
        row_count=1,
        raw_storage_key="raw/forecast",
        raw_payload={},
    )
    user = TrackedUser(
        telegram_user_id=uuid4().int % 1_000_000,
        policy_version="v1",
        consented_at=datetime.now(UTC),
    )
    db_session.add_all([snapshot, user])
    await db_session.flush()
    target = UserTarget(
        tracked_user_id=user.id,
        competition_group_id=group.id,
        identity_namespace="test:2025",
        applicant_uid_hmac="target-hmac",
    )
    db_session.add(target)
    await db_session.flush()
    value = _input(current_snapshot_id=str(snapshot.id))
    uow = UnitOfWork(lambda: db_session)
    uow.session = db_session
    output = AdmissionProbabilityEngine().calculate(value)
    _, created = await persist_forecast(
        uow, tracked_user_id=user.id, user_target_id=target.id, value=value, output=output
    )
    _, duplicate = await persist_forecast(
        uow, tracked_user_id=user.id, user_target_id=target.id, value=value, output=output
    )
    await db_session.commit()
    assert created is True
    assert duplicate is False
    assert (
        len(
            list(
                (
                    await db_session.scalars(
                        select(ForecastRun).where(ForecastRun.user_target_id == target.id)
                    )
                ).all()
            )
        )
        == 1
    )


@pytest.mark.asyncio
async def test_probabilistic_recompute_uses_three_itmo_snapshots(db_session: AsyncSession) -> None:
    university = University(code="itmo", name="ITMO University", parser_status="active")
    db_session.add(university)
    await db_session.flush()
    group = await CompetitionGroupRepository(db_session).add(
        university_id=university.id,
        campaign_year=2026,
        external_group_id=f"forecast-{uuid4().hex}",
        title="Forecast Group",
        identity_namespace="itmo:2026:portal-code:v1",
        priority_kind="university_enrollment",
        priority_confidence="verified",
    )
    started_at = datetime.now(UTC)
    snapshots = [
        ListSnapshot(
            competition_group_id=group.id,
            campaign_year=2026,
            source_url="https://example.invalid/itmo",
            content_hash=f"{index:x}" * 64,
            fetched_at=started_at + timedelta(minutes=index),
            parser_version="test",
            status="valid",
            row_count=3,
            raw_storage_key=f"raw/itmo-{index}",
            raw_payload={"seat_counts": {"general_competition": 2}},
        )
        for index in range(1, 4)
    ]
    user = TrackedUser(
        telegram_user_id=uuid4().int % 1_000_000,
        policy_version="v1",
        consented_at=started_at,
    )
    db_session.add_all([*snapshots, user])
    await db_session.flush()
    target = UserTarget(
        tracked_user_id=user.id,
        competition_group_id=group.id,
        identity_namespace=group.identity_namespace,
        applicant_uid_hmac="target-hmac",
    )
    db_session.add(target)
    for snapshot in snapshots:
        db_session.add_all(
            [
                Application(
                    snapshot_id=snapshot.id,
                    competition_group_id=group.id,
                    identity_namespace=group.identity_namespace,
                    applicant_uid_hmac="ahead-consent",
                    admission_condition="general_competition",
                    rank=1,
                    enrollment_priority=1,
                    consent=True,
                    competitive_score=300,
                    application_status="active",
                    raw_payload={},
                ),
                Application(
                    snapshot_id=snapshot.id,
                    competition_group_id=group.id,
                    identity_namespace=group.identity_namespace,
                    applicant_uid_hmac="target-hmac",
                    admission_condition="general_competition",
                    rank=2,
                    enrollment_priority=1,
                    consent=True,
                    competitive_score=290,
                    application_status="active",
                    raw_payload={},
                ),
            ]
        )
    await db_session.flush()
    uow = UnitOfWork(lambda: db_session)
    uow.session = db_session

    first = await recompute_probabilistic_forecasts(uow, current_snapshot_id=snapshots[-1].id)
    second = await recompute_probabilistic_forecasts(uow, current_snapshot_id=snapshots[-1].id)
    await db_session.commit()

    forecasts = list(
        (
            await db_session.scalars(
                select(ForecastRun).where(ForecastRun.user_target_id == target.id)
            )
        ).all()
    )
    assert first.created == 0
    assert second.created == 0
    assert first.reason == "university_coverage_incomplete"
    assert forecasts == []


@pytest.mark.asyncio
async def test_complete_itmo_batch_uses_cross_group_priority(db_session: AsyncSession) -> None:
    university = University(code="itmo", name="ITMO University", parser_status="active")
    db_session.add(university)
    await db_session.flush()
    primary = await CompetitionGroupRepository(db_session).add(
        university_id=university.id,
        campaign_year=2026,
        external_group_id=f"primary-{uuid4().hex}",
        title="Primary",
        identity_namespace="itmo:2026:portal-code:v1",
        priority_kind="university_enrollment",
        priority_confidence="verified",
    )
    alternative = await CompetitionGroupRepository(db_session).add(
        university_id=university.id,
        campaign_year=2026,
        external_group_id=f"alternative-{uuid4().hex}",
        title="Alternative",
        identity_namespace="itmo:2026:portal-code:v1",
        priority_kind="university_enrollment",
        priority_confidence="verified",
    )
    started_at = datetime.now(UTC)
    snapshots: list[tuple[ListSnapshot, ListSnapshot]] = []
    for index in range(1, 4):
        batch = {"id": f"batch-{index}", "expected_group_count": 2}
        primary_snapshot = ListSnapshot(
            competition_group_id=primary.id,
            campaign_year=2026,
            source_url="https://example.invalid/primary",
            content_hash=f"a{index}" * 32,
            fetched_at=started_at + timedelta(minutes=index),
            parser_version="test",
            status="valid",
            row_count=2,
            raw_storage_key=f"raw/primary-{index}",
            raw_payload={"seat_counts": {"general_competition": 1}, "ingestion_batch": batch},
        )
        alternative_snapshot = ListSnapshot(
            competition_group_id=alternative.id,
            campaign_year=2026,
            source_url="https://example.invalid/alternative",
            content_hash=f"b{index}" * 32,
            fetched_at=started_at + timedelta(minutes=index),
            parser_version="test",
            status="valid",
            row_count=1,
            raw_storage_key=f"raw/alternative-{index}",
            raw_payload={"seat_counts": {"general_competition": 1}, "ingestion_batch": batch},
        )
        db_session.add_all([primary_snapshot, alternative_snapshot])
        snapshots.append((primary_snapshot, alternative_snapshot))
    user = TrackedUser(
        telegram_user_id=uuid4().int % 1_000_000,
        policy_version="v1",
        consented_at=started_at,
    )
    db_session.add(user)
    await db_session.flush()
    target = UserTarget(
        tracked_user_id=user.id,
        competition_group_id=primary.id,
        identity_namespace=primary.identity_namespace,
        applicant_uid_hmac="target",
    )
    db_session.add(target)
    for primary_snapshot, alternative_snapshot in snapshots:
        db_session.add_all(
            [
                Application(
                    snapshot_id=primary_snapshot.id,
                    competition_group_id=primary.id,
                    identity_namespace=primary.identity_namespace,
                    applicant_uid_hmac="ahead",
                    admission_condition="general_competition",
                    rank=1,
                    enrollment_priority=2,
                    consent=True,
                    competitive_score=300,
                    application_status="active",
                    raw_payload={},
                ),
                Application(
                    snapshot_id=primary_snapshot.id,
                    competition_group_id=primary.id,
                    identity_namespace=primary.identity_namespace,
                    applicant_uid_hmac="target",
                    admission_condition="general_competition",
                    rank=2,
                    enrollment_priority=3,
                    consent=True,
                    competitive_score=290,
                    application_status="active",
                    raw_payload={},
                ),
                Application(
                    snapshot_id=alternative_snapshot.id,
                    competition_group_id=alternative.id,
                    identity_namespace=alternative.identity_namespace,
                    applicant_uid_hmac="ahead",
                    admission_condition="general_competition",
                    rank=1,
                    enrollment_priority=1,
                    consent=True,
                    competitive_score=300,
                    application_status="active",
                    raw_payload={"main_top_priority": True, "highest_passageway_priority": True},
                ),
            ]
        )
    await db_session.flush()
    uow = UnitOfWork(lambda: db_session)
    uow.session = db_session

    outcome = await recompute_probabilistic_forecasts(
        uow, current_snapshot_id=snapshots[-1][0].id
    )

    forecasts = list(
        (
            await db_session.scalars(
                select(ForecastRun).where(ForecastRun.user_target_id == target.id)
            )
        ).all()
    )
    probabilistic = next(item for item in forecasts if item.engine_version == "probabilistic-2")
    assert outcome.created == 1
    assert probabilistic.explanation["candidate_count_ahead"] == 0
    assert probabilistic.explanation["candidate_count_cross_group_excluded"] == 1


def test_higher_priority_enrollment_excludes_candidate_from_target_cohort() -> None:
    target_group_id = uuid4()
    alternative_group_id = uuid4()
    target = Application(
        competition_group_id=target_group_id,
        snapshot_id=uuid4(),
        identity_namespace="itmo:2026:portal-code:v1",
        applicant_uid_hmac="target",
        admission_condition="general_competition",
        rank=2,
        enrollment_priority=2,
        consent=True,
        competitive_score=290,
        application_status="active",
        raw_payload={},
    )
    candidate = Application(
        competition_group_id=target_group_id,
        snapshot_id=uuid4(),
        identity_namespace="itmo:2026:portal-code:v1",
        applicant_uid_hmac="ahead",
        admission_condition="general_competition",
        rank=1,
        enrollment_priority=3,
        consent=True,
        competitive_score=300,
        application_status="active",
        raw_payload={},
    )
    alternative = Application(
        competition_group_id=alternative_group_id,
        snapshot_id=uuid4(),
        identity_namespace="itmo:2026:portal-code:v1",
        applicant_uid_hmac="ahead",
        admission_condition="general_competition",
        rank=1,
        enrollment_priority=1,
        consent=True,
        competitive_score=300,
        application_status="active",
        raw_payload={"main_top_priority": True, "highest_passageway_priority": True},
    )

    cohorts, excluded = _candidate_cohorts(
        [candidate, target], target, {"ahead": [candidate, alternative], "target": [target]}
    )

    assert cohorts == ()
    assert excluded == 1
