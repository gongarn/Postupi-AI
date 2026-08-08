from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx

from packages.parsers.base import BaseUniversityParser


@dataclass(frozen=True)
class FetchedDocument:
    content: bytes
    source_url: str
    content_type: str = "text/html"
    metadata: dict[str, str | int | None] | None = None


# Фетчер получает настройки и возвращает список документов (группы + сами списки).
Fetcher = Callable[[httpx.AsyncClient], Awaitable[tuple[FetchedDocument, ...]]]


@dataclass(frozen=True)
class UniversitySource:
    code: str
    name: str
    parser: type[BaseUniversityParser]
    fetcher: Fetcher
    forecast_eligible: bool = False
    enabled: bool = True
    refresh_minutes: int = 60


SOURCES: dict[str, UniversitySource] = {}
