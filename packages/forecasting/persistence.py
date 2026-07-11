from __future__ import annotations

from uuid import UUID

from packages.forecasting.engine import ForecastInput, ForecastOutput
from packages.persistence.repositories import ForecastRepository
from packages.persistence.uow import UnitOfWork


async def persist_forecast(
    uow: UnitOfWork,
    *,
    tracked_user_id: UUID,
    user_target_id: UUID,
    value: ForecastInput,
    output: ForecastOutput,
) -> tuple[ForecastOutput, bool]:
    if not hasattr(uow, "forecasts"):
        uow.forecasts = ForecastRepository(uow.session)
    existing = await uow.forecasts.get_by_identity(
        user_target_id=user_target_id,
        current_snapshot_id=UUID(value.current_snapshot_id),
        engine_version=output.engine_version,
    )
    if existing is not None:
        return output, False
    await uow.forecasts.add(
        tracked_user_id=tracked_user_id,
        user_target_id=user_target_id,
        current_snapshot_id=UUID(value.current_snapshot_id),
        engine_version=output.engine_version,
        probability_low=output.probability_low,
        probability_high=output.probability_high,
        estimated_rank_min=output.estimated_rank_min,
        estimated_rank_max=output.estimated_rank_max,
        confidence=output.confidence,
        explanation=output.explanation,
    )
    return output, True
