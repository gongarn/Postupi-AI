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
from packages.parsers.html_tables import map_condition

RNIMU_NAMESPACE = "admissions_uid:rnimu:{campaign_year}:v1"
RNIMU_ROOT_URL = "https://ratings.rsmu.ru/data/root.json"


class RnimuParser(BaseUniversityParser):
    """Парсер JSON-API конкурсных списков РНИМУ им. Пирогова.

    Цепочка: root.json → версии → конкурсные группы → список абитуриентов.
    В данных уже анонимизированный код абитуриента (title), ранг (order),
    баллы (total), приоритет, согласие (approval), статус (state).
    """

    parser_version = "rnimu-json-1"

    def __init__(self, *, uid_secret: str, campaign_year: int = 2026) -> None:
        self.uid_secret = uid_secret
        self.campaign_year = campaign_year
        self.identity_namespace = RNIMU_NAMESPACE.format(campaign_year=campaign_year)

    def parse(self, content: bytes, *, source_url: str, fetched_at: datetime) -> ParserResult:
        try:
            data = json.loads(content)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            return ParserResult(ParserResultStatus.FAILED, None, (str(exc),), ())
        program = data.get("program")
        if not isinstance(program, str) or not isinstance(data.get("applicants"), list):
            return ParserResult(
                ParserResultStatus.FAILED, None, ("missing program or applicants",), ()
            )
        condition = map_condition(str(data.get("type", "")))
        plan = data.get("plan")
        applications: list[NormalizedApplication] = []
        raw_uids: set[str] = set()
        for record in data["applicants"]:
            uid = str(record.get("title", "")).strip()
            if not uid:
                continue
            applications.append(
                NormalizedApplication(
                    applicant_uid_hmac=hash_uid(
                        secret=self.uid_secret,
                        identity_namespace=self.identity_namespace,
                        uid=uid,
                    ),
                    identity_namespace=self.identity_namespace,
                    admission_condition=condition,
                    rank=int(record.get("order") or 0),
                    enrollment_priority=_optional_int(record.get("priority")),
                    competitive_score=_optional_float(record.get("total")),
                    application_status=_optional_str(record.get("state")),
                    consent=_optional_bool(record.get("approval")),
                    bvi=bool(record.get("noExam")),
                    raw_payload=_allowed_payload(record),
                )
            )
            raw_uids.add(uid)
        if not applications:
            return ParserResult(ParserResultStatus.FAILED, None, ("no applications",), ())
        content_hash = hashlib.sha256(content).hexdigest()
        group = NormalizedCompetitionGroup(
            university_code="rnimu",
            university_name="РНИМУ им. Н.И. Пирогова",
            campaign_year=self.campaign_year,
            external_group_id=program,
            title=program,
            degree="specialist",
            financing="budget",
            identity_namespace=self.identity_namespace,
            priority_kind="university_enrollment" if _has_priority(applications) else "unknown",
            priority_confidence="strong" if _has_priority(applications) else "unknown",
            seat_counts={condition: _optional_int(plan)},
            source_metadata={"source_format": "rnimu_json", "count": len(applications)},
        )
        snapshot = ParsedSnapshot(
            group=group,
            applications=tuple(applications),
            source_url=source_url,
            fetched_at=fetched_at,
            content_hash=content_hash,
            raw_storage_key=f"sha256/{content_hash[:2]}/{content_hash}.json",
            raw_payload={
                "source_format": "rnimu_json",
                "campaign_year": self.campaign_year,
                "program": program,
                "type": data.get("type"),
                "plan": plan,
                "count": len(applications),
                "unique_uid_count": len(raw_uids),
                "parser_version": self.parser_version,
                "source_hash": content_hash,
            },
            parser_version=self.parser_version,
        )
        return ParserResult(ParserResultStatus.VALID, snapshot, (), ())


_ALLOWED_FIELDS = {
    "order", "title", "total", "priority", "diplomaAvg", "original", "paid",
    "approval", "published", "contract", "right9", "right10", "noExam",
    "highest", "mainHighest", "passHighest", "achievementScore",
    "fullAchievementScore", "achievementScoreGeneral", "fullAchievementScoreGeneral",
    "comment", "state", "orgCode", "rejected",
}


def _allowed_payload(record: dict[str, Any]) -> dict[str, Any]:
    return {key: record[key] for key in _ALLOWED_FIELDS if key in record}


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _optional_str(value: Any) -> str | None:
    return str(value) if value is not None else None


def _optional_bool(value: Any) -> bool | None:
    return bool(value) if value is not None else None


def _has_priority(applications: list[NormalizedApplication]) -> bool:
    return any(app.enrollment_priority is not None for app in applications)
