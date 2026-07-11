from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.persistence.repositories import (
    CompetitionGroupRepository,
    SnapshotRepository,
    UniversityRepository,
    UserRepository,
    UserTargetRepository,
)


class UnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def __aenter__(self) -> "UnitOfWork":
        self.session = self.session_factory()
        self.universities = UniversityRepository(self.session)
        self.competition_groups = CompetitionGroupRepository(self.session)
        self.snapshots = SnapshotRepository(self.session)
        self.users = UserRepository(self.session)
        self.user_targets = UserTargetRepository(self.session)
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if exc_type is None:
            await self.session.commit()
        else:
            await self.session.rollback()
        await self.session.close()
