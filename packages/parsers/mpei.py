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
from packages.parsers.html_tables import extract_tables, header_map, map_condition, to_float, to_int

MPEI_NAMESPACE = "admissions_uid:mpei:{campaign_year}:v1"


class MpeiParser(BaseUniversityParser):
    """SSR-таблицы конкурсных списков НИУ МЭИ (pk.mpei.ru/inform/list*.html).

    Одна страница — одна конкурсная группа (код группы в URL, например list4bacc).
    Данные анонимизированы: «Уникальный код поступающего».
    """

    parser_version = "mpei-ssr-1"

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
        self.identity_namespace = MPEI_NAMESPACE.format(campaign_year=campaign_year)

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
            return ParserResult(
                ParserResultStatus.FAILED, None, ("no code column",), ()
            )
        applications = []
        for index, row in enumerate(rows):
            code = _cell(row, mapping, "code")
            if not code:
                continue
            applications.append(
            NormalizedApplication(
                applicant_uid_hmac=hash_uid(
                    secret=self.uid_secret,
                    identity_namespace=self.identity_namespace,
                    uid=code,
                ),
                identity_namespace=self.identity_namespace,
                admission_condition=map_condition(self.title),
                bvi=_is_bvi_status(_cell(row, mapping, "status")),
                rank=index + 1,
                enrollment_priority=to_int(_cell(row, mapping, "priority")),
                competitive_score=to_float(_cell(row, mapping, "score")),
                application_status=_cell(row, mapping, "status"),
                consent=_consent(_cell(row, mapping, "consent")),
                raw_payload={
                    "score_without_ia": to_float(_cell(row, mapping, "score_no_ia")),
                    "ia_extra": to_float(_cell(row, mapping, "ia_extra")),
                    "dorm": _cell(row, mapping, "dorm"),
                },
            )
            )
        
        if not applications:
            return ParserResult(ParserResultStatus.FAILED, None, ("no applications",), ())
        content_hash = hashlib.sha256(content).hexdigest()
        snapshot = ParsedSnapshot(
            group=NormalizedCompetitionGroup(
                university_code="mpei",
                university_name="НИУ МЭИ",
                campaign_year=self.campaign_year,
                external_group_id=self.group_id,
                title=self.title,
                degree="bachelor",
                financing="budget",
                identity_namespace=self.identity_namespace,
                priority_kind="university_enrollment" if "priority" in mapping else "unknown",
                priority_confidence="strong" if "priority" in mapping else "unknown",
                source_metadata={"source_format": "mpei_ssr", "count": len(applications)},
            ),
            applications=tuple(applications),
            source_url=source_url,
            fetched_at=fetched_at,
            content_hash=content_hash,
            raw_storage_key=f"sha256/{content_hash[:2]}/{content_hash}.html",
            raw_payload={
                "source_format": "mpei_ssr",
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


def _cell(row: list[str], mapping: dict[str, int], key: str) -> str | None:
    index = mapping.get(key)
    if index is None or index >= len(row):
        return None
    return row[index] or None


def _consent(value: str | None) -> bool | None:
    if value is None:
        return None
    lowered = value.lower()
    if lowered in {"да", "yes", "1", "+", "✓", "согласие"}:
        return True
    if lowered in {"нет", "no", "0", "-", "—"}:
        return False
    return None


def _is_bvi_status(value: str | None) -> bool | None:
    if value is None:
        return None
    lowered = value.lower()
    return "бви" in lowered or "без вступительных" in lowered
