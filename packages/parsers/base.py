from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class ParserResultStatus(StrEnum):
    VALID = "valid"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass(frozen=True)
class NormalizedCompetitionGroup:
    university_code: str
    university_name: str
    campaign_year: int
    external_group_id: str
    title: str
    degree: str
    financing: str
    identity_namespace: str
    priority_kind: str = "unknown"
    priority_confidence: str = "unknown"
    seat_counts: dict[str, int | None] | None = None
    source_metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class NormalizedApplication:
    applicant_uid_hmac: str
    identity_namespace: str
    admission_condition: str
    rank: int
    enrollment_priority: int | None
    competitive_score: float | None
    application_status: str | None
    raw_payload: dict[str, Any]


@dataclass(frozen=True)
class ParsedSnapshot:
    group: NormalizedCompetitionGroup
    applications: tuple[NormalizedApplication, ...]
    source_url: str
    fetched_at: datetime
    content_hash: str
    raw_storage_key: str
    raw_payload: dict[str, Any]
    parser_version: str


@dataclass(frozen=True)
class ParserResult:
    status: ParserResultStatus
    snapshot: ParsedSnapshot | None
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


class BaseUniversityParser:
    parser_version = "base-1"

    def parse(self, content: bytes, *, source_url: str, fetched_at: datetime) -> ParserResult:
        raise NotImplementedError
