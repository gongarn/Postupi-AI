from __future__ import annotations

import hashlib
import json
from datetime import datetime
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
from packages.parsers.html_tables import to_float, to_int

GUBKIN_NAMESPACE = "admissions_uid:gubkin:{campaign_year}:v1"


class GubkinParser(BaseUniversityParser):
    """Парсер JSON-API конкурсных списков РГУ нефти и газа им. Губкина.

    Метод get?educationTypeId=..&contestGroupId=.. возвращает список с
    анонимизированным fio (код абитуриента), рангом, баллами, согласием.
    """

    parser_version = "gubkin-json-1"

    def __init__(
        self,
        *,
        uid_secret: str,
        campaign_year: int = 2026,
        group_id: str | None = None,
        title: str | None = None,
        condition: str = "general_competition",
    ) -> None:
        self.uid_secret = uid_secret
        self.campaign_year = campaign_year
        self.group_id = group_id or "unknown"
        self.title = title or group_id or "unknown"
        self.condition = condition
        self.identity_namespace = GUBKIN_NAMESPACE.format(campaign_year=campaign_year)

    def parse(self, content: bytes, *, source_url: str, fetched_at: datetime) -> ParserResult:
        try:
            payload = json.loads(content)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            return ParserResult(ParserResultStatus.FAILED, None, (str(exc),), ())
        items = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            return ParserResult(ParserResultStatus.FAILED, None, ("no data list",), ())
        applications: list[NormalizedApplication] = []
        seen: set[str] = set()
        for record in items:
            if not isinstance(record, dict):
                continue
            uid = str(record.get("fio", "")).strip()
            if not uid or uid in seen:
                continue
            seen.add(uid)
            applications.append(
                NormalizedApplication(
                    applicant_uid_hmac=hash_uid(
                        secret=self.uid_secret,
                        identity_namespace=self.identity_namespace,
                        uid=uid,
                    ),
                    identity_namespace=self.identity_namespace,
                    admission_condition=self.condition,
                    rank=to_int(_value(record, "position")) or 0,
                    enrollment_priority=to_int(_value(record, "priority")),
                    competitive_score=to_float(_value(record, "totalBalls")),
                    application_status=None,
                    consent=_bool(record.get("enrollmentAgreement")),
                    raw_payload={
                        "entrance_balls": to_float(_value(record, "entranceBalls")),
                        "ia_balls": to_float(_value(record, "individualAchievementsBalls")),
                        "need_hostel": _bool(record.get("needHostel")),
                        "benefit": _value(record, "benefit"),
                        "offer_number": _value(record, "offerNumber"),
                        "main_highest_priority": _value(record, "mainHighestPriority"),
                        "balls_by_subjects": [
                            {
                                "name": str(item.get("name", "")),
                                "ball": to_float(_value(item, "ball")),
                            }
                            for item in record.get("ballsBySubjects", [])
                            if isinstance(item, dict)
                        ][:8],
                    },
                )
            )
        if not applications:
            return ParserResult(ParserResultStatus.FAILED, None, ("no applications",), ())
        content_hash = hashlib.sha256(content).hexdigest()
        snapshot = ParsedSnapshot(
            group=NormalizedCompetitionGroup(
                university_code="gubkin",
                university_name="РГУ нефти и газа (НИУ) им. И.М. Губкина",
                campaign_year=self.campaign_year,
                external_group_id=f"{self.group_id}:{self.condition}",
                title=self.title,
                degree="bachelor",
                financing="budget",
                identity_namespace=self.identity_namespace,
                priority_kind="university_enrollment" if _has_priority(applications) else "unknown",
                priority_confidence="strong" if _has_priority(applications) else "unknown",
                source_metadata={"source_format": "gubkin_json", "count": len(applications)},
            ),
            applications=tuple(applications),
            source_url=source_url,
            fetched_at=fetched_at,
            content_hash=content_hash,
            raw_storage_key=f"sha256/{content_hash[:2]}/{content_hash}.json",
            raw_payload={
                "source_format": "gubkin_json",
                "campaign_year": self.campaign_year,
                "group_id": self.group_id,
                "title": self.title,
                "condition": self.condition,
                "count": len(applications),
                "parser_version": self.parser_version,
                "source_hash": content_hash,
            },
            parser_version=self.parser_version,
        )
        return ParserResult(ParserResultStatus.VALID, snapshot, (), ())


def _value(record: dict[str, Any], key: str) -> str | None:
    value = record.get(key)
    if value is None:
        return None
    return str(value)


def _bool(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)


def _has_priority(applications: list[NormalizedApplication]) -> bool:
    return any(app.enrollment_priority is not None for app in applications)
