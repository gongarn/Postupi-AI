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


def test_hse_fresh_snapshot_derives_selection_before_applicant_request() -> None:
    requests: list[httpx.Request] = []
    discovery = {
        "filials": [{
            "trainingDirections": [{"educationPrograms": [{
                "educationLevel": {"code": "bachelor"},
                "competitiveGroups": [{
                    "id": "fresh-group",
                    "placeType": {"id": "fresh-place"},
                    "setOfCompetitiveGroup": {"id": "fresh-set"},
                }],
            }]}]
        }]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/competitve-group"):
            return httpx.Response(
                200, headers={"content-type": "application/json"}, json=discovery
            )
        if request.url.path.endswith("/fresh-group"):
            return httpx.Response(
                200, headers={"content-type": "application/json"}, json={"placeCount": 1}
            )
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            json={
                "content": [],
                "number": 0,
                "size": 50,
                "totalElements": 0,
                "totalPages": 0,
            },
        )

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            snapshot = await HseClient(client).fetch_fresh_snapshot()
            assert snapshot.selection["competitiveGroupId"] == "fresh-group"

    asyncio.run(run())
    applicant = requests[-1]
    assert applicant.url.path.endswith("/applicant")
    assert applicant.url.params["competitiveGroupId"] == "fresh-group"
    assert applicant.url.params["setOfCompetitiveGroupId"] == "fresh-set"
    assert applicant.url.params["placeType"] == "fresh-place"
    assert applicant.url.params["level"] == "bachelor"
