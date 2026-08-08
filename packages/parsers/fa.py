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

FA_NAMESPACE = "admissions_uid:fa:{campaign_year}:v1"


class FaParser(BaseUniversityParser):
    """SSR-таблица конкурсного списка Финансового университета.

    Одна страница (listabit.php) содержит все конкурсные группы сразу;
    snapshot строится на вуз целиком, группа/факультет/финансирование
    сохраняются в raw_payload каждого заявления.
    """

    parser_version = "fa-ssr-1"

    def __init__(self, *, uid_secret: str, campaign_year: int = 2026) -> None:
        self.uid_secret = uid_secret
        self.campaign_year = campaign_year
        self.identity_namespace = FA_NAMESPACE.format(campaign_year=campaign_year)

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
                admission_condition=map_condition(_cell(row, mapping, "contest")),
                rank=index + 1,
                enrollment_priority=to_int(_cell(row, mapping, "priority")),
                competitive_score=to_float(_cell(row, mapping, "score")),
                application_status=None,
                consent=_consent(_cell(row, mapping, "consent")),
                raw_payload={
                    "financing": _cell(row, mapping, "financing"),
                    "faculty": _cell(row, mapping, "faculty"),
                    "group": _cell(row, mapping, "group"),
                    "contest": _cell(row, mapping, "contest"),
                    "contract": _cell(row, mapping, "contract"),
                    "ia": to_float(_cell(row, mapping, "ia")),
                    "score_without_ia": to_float(_cell(row, mapping, "score_no_ia")),
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
                university_code="fa",
                university_name="Финансовый университет при Правительстве РФ",
                campaign_year=self.campaign_year,
                external_group_id="all",
                title="Конкурсные списки (все группы)",
                degree="bachelor",
                financing="mixed",
                identity_namespace=self.identity_namespace,
                priority_kind="university_enrollment" if "priority" in mapping else "unknown",
                priority_confidence="strong" if "priority" in mapping else "unknown",
                source_metadata={"source_format": "fa_ssr", "count": len(applications)},
            ),
            applications=tuple(applications),
            source_url=source_url,
            fetched_at=fetched_at,
            content_hash=content_hash,
            raw_storage_key=f"sha256/{content_hash[:2]}/{content_hash}.html",
            raw_payload={
                "source_format": "fa_ssr",
                "campaign_year": self.campaign_year,
                "count": len(applications),
                "parser_version": self.parser_version,
                "source_hash": content_hash,
            },
            parser_version=self.parser_version,
        )
        return ParserResult(ParserResultStatus.VALID, snapshot, (), ())
