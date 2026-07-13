from dataclasses import dataclass
from uuid import UUID

import httpx


class TargetAPIError(Exception):
    pass


class TargetAlreadyExistsError(TargetAPIError):
    pass


@dataclass(frozen=True)
class CompetitionGroup:
    id: UUID
    university_id: UUID
    university_name: str
    title: str


async def list_competition_groups(*, base_url: str, token: str) -> list[CompetitionGroup]:
    async with httpx.AsyncClient(base_url=base_url, timeout=10) as client:
        response = await client.get("/internal/competition-groups", headers=_headers(token))
    _raise_for_error(response)
    return [
        CompetitionGroup(
            id=UUID(item["id"]),
            university_id=UUID(item["university_id"]),
            university_name=item["university_name"],
            title=item["title"],
        )
        for item in response.json()
    ]


async def create_target(
    *,
    base_url: str,
    token: str,
    telegram_user_id: int,
    competition_group_id: UUID,
    applicant_uid: str,
) -> None:
    async with httpx.AsyncClient(base_url=base_url, timeout=10) as client:
        response = await client.post(
            "/internal/user-targets",
            headers=_headers(token),
            json={
                "telegram_user_id": telegram_user_id,
                "competition_group_id": str(competition_group_id),
                "applicant_uid": applicant_uid,
            },
        )
    if response.status_code == 409:
        raise TargetAlreadyExistsError
    _raise_for_error(response)


def _headers(token: str) -> dict[str, str]:
    return {"x-internal-token": token}


def _raise_for_error(response: httpx.Response) -> None:
    if response.is_error:
        raise TargetAPIError
