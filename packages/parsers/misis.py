from __future__ import annotations

import hashlib
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
from packages.parsers.html_tables import (
    extract_tables,
    header_map,
    map_condition,
    to_float,
    to_int,
)
from packages.parsers.mpei import _cell, _consent

MISIS_NAMESPACE = "admissions_uid:misis:{campaign_year}:v1"


class MisisParser(BaseUniversityParser):
    """SSR-страницы конкурсных списков НИТУ МИСИС.

    Одна страница (list/?id=...) — одна конкурсная группа.
    Анонимизированный «Уникальный код».
    """

    parser_version = "misis-ssr-1"

    def __init__(
        self,
        *,
        uid_secret: str,
        campaign_year: int = 2026,
        group_id: str | None = None,
        title: str | None = None,
    ) -> None:
        self.uid_secret = uid_secret
        self.campaign_year = campaign_year
        self.group_id = group_id or "unknown"
        self.title = title or group_id or "unknown"
        self.identity_namespace = MISIS_NAMESPACE.format(campaign_year=campaign_year)

    def parse(self, content: bytes, *, source_url: str, fetched_at: datetime) -> ParserResult:
        try:
            html = content.decode("utf-8", errors="replace")
        except Exception as exc:  # pragma: no cover
            return ParserResult(ParserResultStatus.FAILED, None, (str(exc),), ())
        tables = extract_tables(html)
        if not tables:
            return ParserResult(ParserResultStatus.FAILED, None, ("no tables",), ())
        mapping, rows = header_map(max(tables, key=len))
        if "code" not in mapping:
            return ParserResult(ParserResultStatus.FAILED, None, ("no code column",), ())
        applications = [
            NormalizedApplication(
                applicant_uid_hmac=hash_uid(
                    secret=self.uid_secret,
                    identity_namespace=self.identity_namespace,
                    uid=_cell(row, mapping, "code") or "",
                ),
                identity_namespace=self.identity_namespace,
                admission_condition=map_condition(self.title),
                rank=index + 1,
                enrollment_priority=to_int(_cell(row, mapping, "priority")),
                competitive_score=to_float(_cell(row, mapping, "score")),
                application_status=_cell(row, mapping, "status"),
                consent=_consent(_cell(row, mapping, "consent")),
                bvi=_is_bvi(_cell(row, mapping, "financing")),
                raw_payload={
                    "score_without_ia": to_float(_cell(row, mapping, "score_no_ia")),
                    "ia": to_float(_cell(row, mapping, "ia")),
                    "contract": _cell(row, mapping, "contract"),
                    "advantage": _cell(row, mapping, "advantage"),
                },
            )
            for index, row in enumerate(rows)
            if _cell(row, mapping, "code")
        ]
        if not applications:
            return ParserResult(ParserResultStatus.FAILED, None, ("no applications",), ())
        content_hash = hashlib.sha256(content).hexdigest()
        snapshot = ParsedSnapshot(
            group=NormalizedCompetitionGroup(
                university_code="misis",
                university_name="НИТУ МИСИС",
                campaign_year=self.campaign_year,
                external_group_id=self.group_id,
                title=self.title,
                degree="bachelor",
                financing="budget",
                identity_namespace=self.identity_namespace,
                priority_kind="university_enrollment" if "priority" in mapping else "unknown",
                priority_confidence="strong" if "priority" in mapping else "unknown",
                source_metadata={"source_format": "misis_ssr", "count": len(applications)},
            ),
            applications=tuple(applications),
            source_url=source_url,
            fetched_at=fetched_at,
            content_hash=content_hash,
            raw_storage_key=f"sha256/{content_hash[:2]}/{content_hash}.html",
            raw_payload={
                "source_format": "misis_ssr",
                "campaign_year": self.campaign_year,
                "group_id": self.group_id,
                "title": self.title,
                "count": len(applications),
                "parser_version": self.parser_version,
                "source_hash": content_hash,
            },
            parser_version=self.parser_version,
        )
        return ParserResult(ParserResultStatus.VALID, snapshot, (), ())


def _is_bvi(value: str | None) -> bool | None:
    if value is None:
        return None
    return "бви" in value.lower() or "без вступительных" in value.lower()
