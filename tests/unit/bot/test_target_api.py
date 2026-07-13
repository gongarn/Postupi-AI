from uuid import UUID

import httpx
import pytest

from apps.bot.target_api import TargetAlreadyExistsError, create_target, list_competition_groups


@pytest.mark.asyncio
async def test_list_competition_groups_uses_internal_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-internal-token"] == "test-token"
        return httpx.Response(
            200,
            json=[
                {
                    "id": "a20d78f1-513e-4b67-a95f-bc4922a7b9a1",
                    "university_id": "1b0ff005-5bb9-4b8b-b5e8-cdfed09296bd",
                    "university_name": "ITMO",
                    "title": "Software Engineering",
                }
            ],
        )

    transport = httpx.MockTransport(handler)
    async_client = httpx.AsyncClient

    def client(*args: object, **kwargs: object) -> httpx.AsyncClient:
        return async_client(*args, transport=transport, **kwargs)

    monkeypatch.setattr("apps.bot.target_api.httpx.AsyncClient", client)

    groups = await list_competition_groups(base_url="http://api", token="test-token")

    assert groups[0].id == UUID("a20d78f1-513e-4b67-a95f-bc4922a7b9a1")
    assert groups[0].university_name == "ITMO"


@pytest.mark.asyncio
async def test_create_target_maps_duplicate_to_specific_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(409))
    async_client = httpx.AsyncClient

    def client(*args: object, **kwargs: object) -> httpx.AsyncClient:
        return async_client(*args, transport=transport, **kwargs)

    monkeypatch.setattr("apps.bot.target_api.httpx.AsyncClient", client)

    with pytest.raises(TargetAlreadyExistsError):
        await create_target(
            base_url="http://api",
            token="test-token",
            telegram_user_id=1,
            competition_group_id=UUID("a20d78f1-513e-4b67-a95f-bc4922a7b9a1"),
            applicant_uid="000123",
        )
