from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.persistence.models import (
    CompetitionGroup,
    ListSnapshot,
    TrackedUser,
    University,
    UserTarget,
)


class UniversityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, university_id: UUID) -> University | None:
        return cast(University | None, await self.session.get(University, university_id))

    async def get_by_code(self, code: str) -> University | None:
        return cast(
            University | None,
            await self.session.scalar(select(University).where(University.code == code)),
        )

    async def add(self, *, code: str, name: str, parser_key: str | None = None) -> University:
        entity = University(code=code, name=name, parser_key=parser_key)
        self.session.add(entity)
        await self.session.flush()
        return entity


class CompetitionGroupRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, group_id: UUID) -> CompetitionGroup | None:
        return cast(CompetitionGroup | None, await self.session.get(CompetitionGroup, group_id))

    async def get_by_external_key(
        self, *, university_id: UUID, campaign_year: int, external_group_id: str
    ) -> CompetitionGroup | None:
        return cast(
            CompetitionGroup | None,
            await self.session.scalar(
                select(CompetitionGroup).where(
                    CompetitionGroup.university_id == university_id,
                    CompetitionGroup.campaign_year == campaign_year,
                    CompetitionGroup.external_group_id == external_group_id,
                )
            ),
        )

    async def add(
        self,
        *,
        university_id: UUID,
        campaign_year: int,
        external_group_id: str,
        title: str,
        identity_namespace: str,
        priority_kind: str = "unknown",
        priority_confidence: str = "unknown",
    ) -> CompetitionGroup:
        entity = CompetitionGroup(
            university_id=university_id,
            campaign_year=campaign_year,
            external_group_id=external_group_id,
            title=title,
            identity_namespace=identity_namespace,
            priority_kind=priority_kind,
            priority_confidence=priority_confidence,
        )
        self.session.add(entity)
        await self.session.flush()
        return entity


class SnapshotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_content(
        self, *, competition_group_id: UUID, source_url: str, content_hash: str
    ) -> ListSnapshot | None:
        return cast(
            ListSnapshot | None,
            await self.session.scalar(
                select(ListSnapshot).where(
                    ListSnapshot.competition_group_id == competition_group_id,
                    ListSnapshot.source_url == source_url,
                    ListSnapshot.content_hash == content_hash,
                )
            ),
        )

    async def add(
        self,
        *,
        competition_group_id: UUID,
        campaign_year: int,
        source_url: str,
        content_hash: str,
        fetched_at: datetime,
        parser_version: str,
        status: str,
        row_count: int,
        raw_storage_key: str,
        raw_payload: dict[str, Any],
    ) -> ListSnapshot:
        entity = ListSnapshot(
            competition_group_id=competition_group_id,
            campaign_year=campaign_year,
            source_url=source_url,
            content_hash=content_hash,
            fetched_at=fetched_at,
            parser_version=parser_version,
            status=status,
            row_count=row_count,
            raw_storage_key=raw_storage_key,
            raw_payload=raw_payload,
        )
        self.session.add(entity)
        await self.session.flush()
        return entity


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: UUID) -> TrackedUser | None:
        return cast(TrackedUser | None, await self.session.get(TrackedUser, user_id))

    async def get_by_telegram_id(self, telegram_user_id: int) -> TrackedUser | None:
        return cast(
            TrackedUser | None,
            await self.session.scalar(
                select(TrackedUser).where(TrackedUser.telegram_user_id == telegram_user_id)
            ),
        )

    async def add(
        self, *, telegram_user_id: int, policy_version: str, consented_at: datetime
    ) -> TrackedUser:
        entity = TrackedUser(
            telegram_user_id=telegram_user_id,
            policy_version=policy_version,
            consented_at=consented_at,
        )
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def delete(self, user_id: UUID) -> None:
        entity = await self.session.get(TrackedUser, user_id)
        if entity is not None:
            await self.session.delete(entity)
            await self.session.flush()


class UserTargetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_user(self, tracked_user_id: UUID) -> list[UserTarget]:
        result = await self.session.scalars(
            select(UserTarget).where(UserTarget.tracked_user_id == tracked_user_id)
        )
        return list(result)

    async def add(
        self,
        *,
        tracked_user_id: UUID,
        competition_group_id: UUID,
        identity_namespace: str,
        applicant_uid_hmac: str,
    ) -> UserTarget:
        entity = UserTarget(
            tracked_user_id=tracked_user_id,
            competition_group_id=competition_group_id,
            identity_namespace=identity_namespace,
            applicant_uid_hmac=applicant_uid_hmac,
        )
        self.session.add(entity)
        await self.session.flush()
        return entity
