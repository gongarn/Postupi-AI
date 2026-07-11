from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.bot.presenters import TrackView
from packages.persistence.models import (
    ApplicationEvent,
    CompetitionGroup,
    ForecastRun,
    ListSnapshot,
    SnapshotStatus,
    TrackedUser,
    University,
    UserTarget,
)


async def list_track_views(session: AsyncSession, telegram_user_id: int) -> list[TrackView]:
    user = await session.scalar(
        select(TrackedUser).where(TrackedUser.telegram_user_id == telegram_user_id)
    )
    if user is None:
        return []
    targets = list(
        (
            await session.scalars(
                select(UserTarget).where(UserTarget.tracked_user_id == user.id)
            )
        ).all()
    )
    return [await _view_for_target(session, target) for target in targets]


async def get_track_view(
    session: AsyncSession, telegram_user_id: int, target_id: UUID
) -> TrackView | None:
    target = await session.scalar(
        select(UserTarget)
        .join(TrackedUser)
        .where(
            UserTarget.id == target_id,
            TrackedUser.telegram_user_id == telegram_user_id,
        )
    )
    return await _view_for_target(session, target) if target is not None else None


async def _view_for_target(session: AsyncSession, target: UserTarget) -> TrackView:
    group, university = (
        await session.execute(
            select(CompetitionGroup, University)
            .join(University, University.id == CompetitionGroup.university_id)
            .where(CompetitionGroup.id == target.competition_group_id)
        )
    ).one()
    snapshot = await session.scalar(
        select(ListSnapshot)
        .where(
            ListSnapshot.competition_group_id == group.id,
            ListSnapshot.status == SnapshotStatus.VALID,
        )
        .order_by(ListSnapshot.fetched_at.desc())
    )
    forecast = (
        await session.scalar(
            select(ForecastRun)
            .where(ForecastRun.user_target_id == target.id)
            .where(ForecastRun.current_snapshot_id == snapshot.id)
            .order_by(ForecastRun.id.desc())
        )
        if snapshot is not None
        else None
    )
    event_counts: dict[str, int] = {}
    if snapshot is not None:
        rows = await session.execute(
            select(ApplicationEvent.event_type, func.count(ApplicationEvent.id))
            .where(ApplicationEvent.current_snapshot_id == snapshot.id)
            .group_by(ApplicationEvent.event_type)
        )
        event_counts = {event_type: int(count) for event_type, count in rows}
    return TrackView(
        target_id=str(target.id),
        university_name=university.name,
        external_group_id=group.external_group_id,
        campaign_year=group.campaign_year,
        title=group.title,
        snapshot_status=snapshot.status if snapshot is not None else "нет snapshot",
        probability_low=forecast.probability_low if forecast else None,
        probability_high=forecast.probability_high if forecast else None,
        confidence=forecast.confidence if forecast else None,
        event_counts=event_counts,
        explanation=forecast.explanation if forecast else None,
    )
