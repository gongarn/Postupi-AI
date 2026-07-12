from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict
from datetime import datetime
from html import unescape
from typing import Any

from packages.common.uid import hash_uid
from packages.parsers.base import (
    BaseUniversityParser,
    NormalizedApplication,
    NormalizedCompetitionGroup,
    ParsedSnapshot,
    ParserResult,
    ParserResultStatus,
)

ITMO_NAMESPACE = "itmo:2026:portal-code:v1"
ITMO_GROUP_ID = "2334"
ITMO_2025_NAMESPACE = "admissions_uid:observed_cross_university:2025"
ITMO_2025_GROUP_ID = "2199"
ITMO_2026_NAMESPACE = ITMO_NAMESPACE
ITMO_SOURCE_URL = (
    "https://abit.itmo.ru/rating/bachelor/budget/2334"
)
_CONDITIONS = (
    "general_competition",
    "by_special_quota",
    "by_target_quota",
    "by_unusual_quota",
    "without_entry_tests",
)
_ALLOWED_PAYLOAD_FIELDS = {
    "exam_scores",
    "ia_scores",
    "total_scores",
    "position",
    "priority",
    "exam_type",
    "status",
    "has_approved_contract",
    "highest_passageway_priority",
    "is_detailed_target_quota",
    "is_have_advantages",
    "is_published_in_work_in_russia",
    "is_send_agreement",
    "is_special_b_category",
    "main_top_priority",
    "olympiad",
    "offer_number",
    "target_achievements",
    "target_organization_number",
}


class ItmoParser(BaseUniversityParser):
    parser_version = "itmo-next-data-1"

    def __init__(
        self,
        *,
        uid_secret: str,
        campaign_year: int = 2026,
        competitive_group_id: str = ITMO_GROUP_ID,
        identity_namespace: str | None = None,
    ) -> None:
        if campaign_year < 2000:
            raise ValueError("invalid ITMO campaign year")
        self.uid_secret = uid_secret
        self.campaign_year = campaign_year
        self.competitive_group_id = competitive_group_id
        self.identity_namespace = identity_namespace or (
            ITMO_2025_NAMESPACE if campaign_year == 2025 else ITMO_2026_NAMESPACE
            if campaign_year == 2026
            else f"itmo:{campaign_year}:portal-code:v1"
        )
        self.parser_version = f"itmo-next-data-{campaign_year}"

    def parse(self, content: bytes, *, source_url: str, fetched_at: datetime) -> ParserResult:
        try:
            data = _extract_next_data(content)
            page = data["props"]["pageProps"]
            program = page["programList"]
            direction = program["direction"]
            _validate_metadata(data, direction, self.competitive_group_id)
            applications: list[NormalizedApplication] = []
            for condition in _CONDITIONS:
                for record in program[condition]:
                    applications.append(self._application(record, condition))
            _validate_applications(applications)
            content_hash = hashlib.sha256(content).hexdigest()
            snapshot = ParsedSnapshot(
                group=NormalizedCompetitionGroup(
                    university_code="itmo",
                    university_name="ITMO University",
                    campaign_year=self.campaign_year,
                    external_group_id=str(direction["competitive_group_id"]),
                    title=str(direction["direction_title"]),
                    degree=str(page["degree"]),
                    financing=str(page["financing"]),
                    identity_namespace=self.identity_namespace,
                    source_metadata={"source_format": "itmo_next_data"},
                    seat_counts=_seat_counts(direction),
                ),
                applications=tuple(applications),
                source_url=source_url,
                fetched_at=fetched_at,
                content_hash=content_hash,
                raw_storage_key=f"sha256/{content_hash[:2]}/{content_hash}.html",
                raw_payload={
                    "source_format": "itmo_next_data",
                    "campaign_year": self.campaign_year,
                    "degree": str(page["degree"]),
                    "financing": str(page["financing"]),
                    "external_group_id": str(direction["competitive_group_id"]),
                    "parser_version": self.parser_version,
                    "record_counts": {
                        condition: len(program[condition]) for condition in _CONDITIONS
                    },
                    "source_hash": content_hash,
                },
                parser_version=self.parser_version,
            )
            raw_uids = {
                str(record["sspvo_id"])
                for condition in _CONDITIONS
                for record in program[condition]
            }
            _validate_no_raw_uids(snapshot, raw_uids)
            return ParserResult(ParserResultStatus.VALID, snapshot, (), ())
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return ParserResult(
                ParserResultStatus.FAILED,
                None,
                (f"parse failed: {type(exc).__name__}",),
                (),
            )

    def _application(self, record: dict[str, Any], condition: str) -> NormalizedApplication:
        uid = record["sspvo_id"]
        if not isinstance(uid, str) or not uid.strip():
            raise ValueError("missing applicant UID")
        expected_keys = _ALLOWED_PAYLOAD_FIELDS | {"sspvo_id", "link", "disciplines_scores"}
        if set(record) != expected_keys:
            raise ValueError("unexpected record schema")
        payload = {key: record[key] for key in _ALLOWED_PAYLOAD_FIELDS if key in record}
        return NormalizedApplication(
            applicant_uid_hmac=hash_uid(
                secret=self.uid_secret, identity_namespace=self.identity_namespace, uid=uid
            ),
            identity_namespace=self.identity_namespace,
            admission_condition=condition,
            rank=int(record["position"]),
            enrollment_priority=int(record["priority"]) if record["priority"] is not None else None,
            competitive_score=(
                float(record["total_scores"]) if record["total_scores"] is not None else None
            ),
            application_status=str(record["status"]) if record["status"] is not None else None,
            consent=record["is_send_agreement"],
            bvi=condition == "without_entry_tests",
            raw_payload=payload,
        )


def _extract_next_data(content: bytes) -> dict[str, Any]:
    html = content.decode("utf-8", errors="strict")
    match = re.search(
        r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
        html,
        re.S | re.I,
    )
    if match is None:
        raise ValueError("missing next data")
    parsed = json.loads(unescape(match.group(1)))
    if not isinstance(parsed, dict):
        raise ValueError("invalid next data root")
    return parsed


def _validate_metadata(
    data: dict[str, Any], direction: dict[str, Any], competitive_group_id: str
) -> None:
    query = data.get("query")
    if not isinstance(query, dict) or str(query.get("id")) != competitive_group_id:
        raise ValueError("unexpected group metadata")
    if direction.get("competitive_group_id") != int(competitive_group_id):
        raise ValueError("unexpected competitive group")


def _seat_counts(direction: dict[str, Any]) -> dict[str, int | None]:
    fields = {
        "budget_min": "general_competition",
        "special_quota": "by_special_quota",
        "target_reception": "by_target_quota",
    }
    result: dict[str, int | None] = {condition: None for condition in _CONDITIONS}
    for source_field, condition in fields.items():
        value = direction.get(source_field)
        if value is not None:
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError("invalid ITMO seat count")
            result[condition] = value
    return result


def _validate_applications(applications: list[NormalizedApplication]) -> None:
    grouped: dict[str, list[NormalizedApplication]] = {}
    for application in applications:
        grouped.setdefault(application.admission_condition, []).append(application)
        if (
            application.competitive_score is not None
            and not 0 <= application.competitive_score <= 400
        ):
            raise ValueError("score out of range")
    for group in grouped.values():
        ranks = [application.rank for application in group]
        if len(ranks) != len(set(ranks)) or ranks != sorted(ranks):
            raise ValueError("invalid condition rank ordering")


def _validate_no_raw_uids(snapshot: ParsedSnapshot, raw_uids: set[str]) -> None:
    output = asdict(snapshot)
    serialized = json.dumps(output, ensure_ascii=False, default=str)
    if "sspvo_id" in serialized or _contains_exact_string(output, raw_uids):
        raise ValueError("raw UID found in parser output")


def _contains_exact_string(value: Any, forbidden: set[str]) -> bool:
    if isinstance(value, str):
        return value in forbidden
    if isinstance(value, dict):
        return any(_contains_exact_string(item, forbidden) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_contains_exact_string(item, forbidden) for item in value)
    return False
