from __future__ import annotations

import httpx

from packages.parsers.hse import HSE_API_BASE


class HseClient:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self.client = client

    async def fetch_applicants(self, **params: str | int) -> bytes:
        if set(params) != {
            "competitiveGroupId",
            "setOfCompetitiveGroupId",
            "placeType",
            "level",
            "page",
            "size",
            "sort",
        }:
            raise ValueError("HSE applicant request contract mismatch")
        own_client = self.client is None
        client = self.client or httpx.AsyncClient(timeout=30)
        try:
            return await self._get_json(client, "/applicant", params)
        finally:
            if own_client:
                await client.aclose()

    async def fetch_competitive_groups(self) -> bytes:
        return await self._request_json("/competitve-group")

    async def fetch_competitive_list(self, **params: str | int) -> bytes:
        return await self._request_json("/competitve-group/competitive-list", params)

    async def fetch_group_header(self, competitive_group_id: str) -> bytes:
        return await self._request_json(f"/competitve-group/{competitive_group_id}")

    async def fetch_quota(self, *, set_of_competitive_group_id: str, place_type_id: str) -> bytes:
        return await self._request_json(
            "/quota",
            {
                "setOfCompetitiveGroupId": set_of_competitive_group_id,
                "placeTypeId": place_type_id,
            },
        )

    async def _request_json(
        self, path: str, params: dict[str, str | int] | None = None
    ) -> bytes:
        own_client = self.client is None
        client = self.client or httpx.AsyncClient(timeout=30)
        try:
            return await self._get_json(client, path, params or {})
        finally:
            if own_client:
                await client.aclose()

    @staticmethod
    async def _get_json(
        client: httpx.AsyncClient, path: str, params: dict[str, str | int]
    ) -> bytes:
        response = await client.get(f"{HSE_API_BASE}{path}", params=params)
        response.raise_for_status()
        if "application/json" not in response.headers.get("content-type", ""):
            raise ValueError("HSE response is not JSON")
        return response.content
