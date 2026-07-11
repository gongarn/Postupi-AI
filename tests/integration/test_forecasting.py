from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.forecasting.engine import AdmissionProbabilityEngine
from packages.forecasting.persistence import persist_forecast
from packages.persistence.models import ForecastRun, ListSnapshot, TrackedUser, UserTarget
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
    assert len(list((await db_session.scalars(select(ForecastRun))).all())) == 1
