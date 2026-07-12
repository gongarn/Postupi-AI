from __future__ import annotations

import hashlib
import json
from datetime import datetime

from packages.common.uid import hash_uid
from packages.parsers.base import (
    BaseUniversityParser,
    NormalizedApplication,
    NormalizedCompetitionGroup,
    ParsedSnapshot,
    ParserResult,
    ParserResultStatus,
)

HSE_API_BASE = "https://pk.hse.ru/admissions/api"
HSE_NAMESPACE = "hse:{campaign_year}:idEpgu:v1"
HSE_PARSER_VERSION = "hse-json-1"
HSE_APPLICANT_FIELDS = {
    "idEpgu",
    "indexNumberInRegList",
    "indexNumberInCompList",
    "priority",
    "isConcertToEnrollment",
    "isWithoutExamsAdmReasonBool",
    "withoutExamsAdmReason",
    "isAllScoresSatisfied",
    "participantStatus",
    "sumCompetitiveScore",
    "sumEntranceTestScore",
    "achievementsSum",
    "documentType",
}


class HseParser(BaseUniversityParser):
    parser_version = HSE_PARSER_VERSION

    def __init__(
        self,
        *,
        uid_secret: str,
        campaign_year: int,
        competitive_group_id: str,
        set_of_competitive_group_id: str,
        place_type: str,
        level: str,
        title: str,
        place_count: int,
        list_mode: str,
    ) -> None:
        if list_mode not in {"registration", "competition"}:
            raise ValueError("ambiguous HSE list mode")
        if place_count < 0:
            raise ValueError("invalid HSE place count")
        self.uid_secret = uid_secret
        self.campaign_year = campaign_year
        self.competitive_group_id = competitive_group_id
        self.set_of_competitive_group_id = set_of_competitive_group_id
        self.place_type = place_type
        self.level = level
        self.title = title
        self.place_count = place_count
        self.list_mode = list_mode
        self.identity_namespace = HSE_NAMESPACE.format(campaign_year=campaign_year)

    def parse(self, content: bytes, *, source_url: str, fetched_at: datetime) -> ParserResult:
        try:
            data = json.loads(content)
            applications = self._applications(data)
            content_hash = hashlib.sha256(content).hexdigest()
            snapshot = ParsedSnapshot(
                group=NormalizedCompetitionGroup(
                    university_code="hse",
                    university_name="HSE University",
                    campaign_year=self.campaign_year,
                    external_group_id=(
                        f"{self.competitive_group_id}:"
                        f"{self.set_of_competitive_group_id}:{self.place_type}"
                    ),
                    title=self.title,
                    degree=self.level,
                    financing=self.place_type,
                    identity_namespace=self.identity_namespace,
                    seat_counts={"place_count": self.place_count},
                    source_metadata={
                        "source_format": "hse_public_json",
                        "list_mode": self.list_mode,
                    },
                ),
                applications=tuple(applications),
                source_url=source_url,
                fetched_at=fetched_at,
                content_hash=content_hash,
                raw_storage_key=f"sha256/{content_hash[:2]}/{content_hash}.json",
                raw_payload={
                    "source_format": "hse_public_json",
                    "campaign_year": self.campaign_year,
                    "external_group_id": (
                        f"{self.competitive_group_id}:"
                        f"{self.set_of_competitive_group_id}:{self.place_type}"
                    ),
                    "place_count": self.place_count,
                    "list_mode": self.list_mode,
                    "record_count": len(applications),
                    "source_hash": content_hash,
                },
                parser_version=self.parser_version,
            )
            return ParserResult(ParserResultStatus.VALID, snapshot, (), ())
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return ParserResult(
                ParserResultStatus.FAILED,
                None,
                (f"parse failed: {type(exc).__name__}",),
                (),
            )

    def _applications(self, data: object) -> list[NormalizedApplication]:
        if not isinstance(data, dict) or not isinstance(data.get("content"), list):
            raise ValueError("invalid HSE applicant response")
        for key in ("number", "size", "totalElements", "totalPages"):
            if not isinstance(data.get(key), int) or isinstance(data[key], bool):
                raise ValueError("missing HSE pagination metadata")
        expected_rank = (
            "indexNumberInRegList"
            if self.list_mode == "registration"
            else "indexNumberInCompList"
        )
        result: list[NormalizedApplication] = []
        ranks: list[int] = []
        for record in data["content"]:
            if not isinstance(record, dict) or not HSE_APPLICANT_FIELDS <= set(record):
                raise ValueError("missing HSE applicant fields")
            uid = record["idEpgu"]
            rank = record[expected_rank]
            if not isinstance(uid, str) or not uid.strip():
                raise ValueError("missing HSE applicant identity")
            if not isinstance(rank, int) or isinstance(rank, bool) or rank <= 0:
                raise ValueError("invalid HSE applicant rank")
            if self.list_mode == "competition" and record[expected_rank] is None:
                raise ValueError("missing HSE competition rank")
            if not isinstance(record["priority"], int) or isinstance(record["priority"], bool):
                raise ValueError("invalid HSE priority")
            if not isinstance(record["isConcertToEnrollment"], bool):
                raise ValueError("invalid HSE consent")
            if not isinstance(record["isWithoutExamsAdmReasonBool"], bool):
                raise ValueError("invalid HSE BVI flag")
            if not isinstance(record["withoutExamsAdmReason"], str):
                raise ValueError("invalid HSE BVI reason")
            ranks.append(rank)
            bvi = record["isWithoutExamsAdmReasonBool"]
            result.append(
                NormalizedApplication(
                    applicant_uid_hmac=hash_uid(
                        secret=self.uid_secret,
                        identity_namespace=self.identity_namespace,
                        uid=uid,
                    ),
                    identity_namespace=self.identity_namespace,
                    admission_condition="without_entry_tests" if bvi else "general_competition",
                    rank=rank,
                    enrollment_priority=record["priority"],
                    competitive_score=_number(record["sumCompetitiveScore"]),
                    application_status=record["participantStatus"],
                    consent=record["isConcertToEnrollment"],
                    bvi=bvi,
                    raw_payload={
                        key: record[key]
                        for key in HSE_APPLICANT_FIELDS
                        if key not in {"idEpgu", "indexNumberInRegList", "indexNumberInCompList"}
                    }
                    | {"bvi": bvi},
                )
            )
        if ranks != sorted(ranks) or len(ranks) != len(set(ranks)):
            raise ValueError("invalid HSE rank ordering")
        return result


def _number(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("invalid HSE score")
    if not 0 <= value <= 400:
        raise ValueError("HSE score out of range")
    return float(value)
