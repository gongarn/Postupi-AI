from __future__ import annotations

import httpx

from packages.parsers.registry import FetchedDocument

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.5",
}


async def fetch_document(
    url: str,
    *,
    client: httpx.AsyncClient,
    headers: dict[str, str] | None = None,
    content_type: str = "text/html",
) -> FetchedDocument:
    response = await client.get(url, headers={**_DEFAULT_HEADERS, **(headers or {})})
    response.raise_for_status()
    return FetchedDocument(
        content=response.content,
        source_url=str(response.url),
        content_type=content_type,
    )
