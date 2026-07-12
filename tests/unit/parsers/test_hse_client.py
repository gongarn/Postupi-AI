import asyncio

import httpx
import pytest

from packages.parsers.hse_client import HseClient


def test_hse_client_uses_pinned_json_contract() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            content=b'{"content": []}',
        )

    async def run() -> bytes:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await HseClient(client).fetch_applicants(
                competitiveGroupId="g",
                setOfCompetitiveGroupId="s",
                placeType="p",
                level="bachelor",
                page=0,
                size=50,
                sort="index_number_in_reg_list",
            )

    assert asyncio.run(run()) == b'{"content": []}'
    assert requests[0].url.path.endswith("/admissions/api/applicant")
    assert requests[0].url.params["sort"] == "index_number_in_reg_list"


def test_hse_client_rejects_contract_drift() -> None:
    with pytest.raises(ValueError, match="contract mismatch"):
        asyncio.run(
            HseClient().fetch_applicants(
                competitiveGroupId="g",
                setOfCompetitiveGroupId="s",
                placeType="p",
                level="bachelor",
                page=0,
                size=50,
            )
        )


def test_hse_client_exposes_pinned_source_endpoints() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200, headers={"content-type": "application/json"}, content=b"{}"
        )

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            source = HseClient(client)
            await source.fetch_competitive_groups()
            await source.fetch_competitive_list(educationLevel="bachelor")
            await source.fetch_group_header("group")
            await source.fetch_quota(set_of_competitive_group_id="set", place_type_id="place")

    asyncio.run(run())
    assert [request.url.path for request in requests] == [
        "/admissions/api/competitve-group",
        "/admissions/api/competitve-group/competitive-list",
        "/admissions/api/competitve-group/group",
        "/admissions/api/quota",
    ]
