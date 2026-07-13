from datetime import UTC, datetime
from hmac import compare_digest
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from apps.api.dependencies import get_engine
from packages.common.config import Settings, get_settings, require_uid_hmac_secret
from packages.common.uid import hash_uid, normalize_uid
from packages.persistence.models import CompetitionGroup, University
from packages.persistence.repositories import UserRepository, UserTargetRepository

router = APIRouter(prefix="/internal", tags=["internal"])


class CompetitionGroupResponse(BaseModel):
    id: UUID
    university_id: UUID
    university_name: str
    title: str


class CreateUserTargetRequest(BaseModel):
    telegram_user_id: int
    competition_group_id: UUID
    applicant_uid: str = Field(min_length=1, max_length=255)


class CreateUserTargetResponse(BaseModel):
    id: UUID


def require_internal_token(
    x_internal_token: Annotated[str | None, Header()],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    if settings.internal_api_token is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    expected = settings.internal_api_token.get_secret_value()
    if not expected or x_internal_token is None or not compare_digest(x_internal_token, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


@router.get("/competition-groups", response_model=list[CompetitionGroupResponse])
async def list_competition_groups(
    engine: Annotated[AsyncEngine, Depends(get_engine)],
    _: Annotated[None, Depends(require_internal_token)],
) -> list[CompetitionGroupResponse]:
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        result = await session.execute(
            select(CompetitionGroup, University)
            .join(University, CompetitionGroup.university_id == University.id)
            .where(~University.code.startswith("test-"))
            .order_by(University.name, CompetitionGroup.title)
        )
        return [
            CompetitionGroupResponse(
                id=group.id,
                university_id=university.id,
                university_name=university.name,
                title=group.title,
            )
            for group, university in result.tuples()
        ]


@router.post(
    "/user-targets",
    response_model=CreateUserTargetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_user_target(
    payload: CreateUserTargetRequest,
    engine: Annotated[AsyncEngine, Depends(get_engine)],
    settings: Annotated[Settings, Depends(get_settings)],
    _: Annotated[None, Depends(require_internal_token)],
) -> CreateUserTargetResponse:
    try:
        applicant_uid = normalize_uid(payload.applicant_uid)
    except TypeError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY) from exc
    if not applicant_uid:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        group = await session.get(CompetitionGroup, payload.competition_group_id)
        if group is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        user_repository = UserRepository(session)
        user = await user_repository.get_by_telegram_id(payload.telegram_user_id)
        if user is None:
            user = await user_repository.add(
                telegram_user_id=payload.telegram_user_id,
                policy_version="v1",
                consented_at=datetime.now(UTC),
            )
        target = await UserTargetRepository(session).add(
            tracked_user_id=user.id,
            competition_group_id=group.id,
            identity_namespace=group.identity_namespace,
            applicant_uid_hmac=hash_uid(
                secret=require_uid_hmac_secret(settings),
                identity_namespace=group.identity_namespace,
                uid=applicant_uid,
            ),
        )
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT) from exc
    return CreateUserTargetResponse(id=target.id)
