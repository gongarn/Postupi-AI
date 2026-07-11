from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from packages.persistence.models import ApplicationEvent


class EventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_ignore_duplicate(
        self,
        *,
        competition_group_id: UUID,
        applicant_uid_hmac: str,
        identity_namespace: str,
        previous_snapshot_id: UUID,
        current_snapshot_id: UUID,
        previous_admission_condition: str | None,
        current_admission_condition: str | None,
        event_type: str,
        before_json: dict[str, Any],
        after_json: dict[str, Any],
        diff_version: str,
    ) -> bool:
        previous_condition = (
            ApplicationEvent.previous_admission_condition.is_(None)
            if previous_admission_condition is None
            else ApplicationEvent.previous_admission_condition == previous_admission_condition
        )
        current_condition = (
            ApplicationEvent.current_admission_condition.is_(None)
            if current_admission_condition is None
            else ApplicationEvent.current_admission_condition == current_admission_condition
        )
        duplicate = await self.session.scalar(
            select(ApplicationEvent.id).where(
                ApplicationEvent.previous_snapshot_id == previous_snapshot_id,
                ApplicationEvent.current_snapshot_id == current_snapshot_id,
                ApplicationEvent.applicant_uid_hmac == applicant_uid_hmac,
                ApplicationEvent.event_type == event_type,
                previous_condition,
                current_condition,
            )
        )
        if duplicate is not None:
            return False
        statement = (
            insert(ApplicationEvent)
            .values(
                competition_group_id=competition_group_id,
                applicant_uid_hmac=applicant_uid_hmac,
                identity_namespace=identity_namespace,
                previous_snapshot_id=previous_snapshot_id,
                current_snapshot_id=current_snapshot_id,
                previous_admission_condition=previous_admission_condition,
                current_admission_condition=current_admission_condition,
                event_type=event_type,
                before_json=before_json,
                after_json=after_json,
                diff_version=diff_version,
            )
            .on_conflict_do_nothing()
            .returning(ApplicationEvent.id)
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none() is not None

    async def count_for_pair(self, previous_snapshot_id: UUID, current_snapshot_id: UUID) -> int:
        value = await self.session.scalar(
            select(func.count(ApplicationEvent.id)).where(
                ApplicationEvent.previous_snapshot_id == previous_snapshot_id,
                ApplicationEvent.current_snapshot_id == current_snapshot_id,
            )
        )
        return int(value or 0)
