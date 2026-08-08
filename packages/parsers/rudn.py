from __future__ import annotations

import hashlib
import re
from datetime import datetime
from html import unescape

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
    to_float,
    to_int,
)
from packages.parsers.mpei import _cell, _consent

RUDN_NAMESPACE = "admissions_uid:rudn:{campaign_year}:v1"


class RudnParser(BaseUniversityParser):
    """SSR-страница конкурсного списка РУДН (competition_list/<id>/).

    Анонимизированный «УИ» (уникальный идентификатор), приоритет, баллы,
    договор. Условие/финансирование передаются фетчером из метаданных страницы.
    """

    parser_version = "rudn-ssr-1"

    def __init__(
        self,
        *,
        uid_secret: str,
        campaign_year: int = 2026,
        group_id: str | None = None,
        title: str | None = None,
        condition: str = "general_competition",
        financing: str = "mixed",
    ) -> None:
        self.uid_secret = uid_secret
        self.campaign_year = campaign_year
        self.group_id = group_id or "unknown"
        self.title = title or group_id or "unknown"
        self.condition = condition
        self.financing = financing
        self.identity_namespace = RUDN_NAMESPACE.format(campaign_year=campaign_year)

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
        seat_count = _seat_from_page(html)
        applications = [
            NormalizedApplication(
                applicant_uid_hmac=hash_uid(
                    secret=self.uid_secret,
                    identity_namespace=self.identity_namespace,
                    uid=_cell(row, mapping, "code") or "",
                ),
                identity_namespace=self.identity_namespace,
                admission_condition=self.condition,
                rank=index + 1,
                enrollment_priority=to_int(_cell(row, mapping, "priority")),
                competitive_score=to_float(_cell(row, mapping, "score")),
                application_status=None,
                consent=_consent(_cell(row, mapping, "consent")),
                raw_payload={
                    "contract": _cell(row, mapping, "contract"),
                    "ia": to_float(_cell(row, mapping, "ia")),
                    "score_without_ia": to_float(_cell(row, mapping, "score_no_ia")),
                    "ovp": _cell(row, mapping, "ovp"),
                    "vpp": _cell(row, mapping, "vpp"),
                },
            )
            for index, row in enumerate(rows)
            if _cell(row, mapping, "code")
        ]
        if not applications:
            return ParserResult(ParserResultStatus.FAILED, None, ("no applications",), ())
        title = _title_from_page(html) or self.title
        content_hash = hashlib.sha256(content).hexdigest()
        snapshot = ParsedSnapshot(
            group=NormalizedCompetitionGroup(
                university_code="rudn",
                university_name="РУДН",
                campaign_year=self.campaign_year,
                external_group_id=self.group_id,
                title=title,
                degree="bachelor",
                financing=self.financing,
                identity_namespace=self.identity_namespace,
                priority_kind="university_enrollment" if "priority" in mapping else "unknown",
                priority_confidence="strong" if "priority" in mapping else "unknown",
                seat_counts={self.condition: seat_count},
                source_metadata={"source_format": "rudn_ssr", "count": len(applications)},
            ),
            applications=tuple(applications),
            source_url=source_url,
            fetched_at=fetched_at,
            content_hash=content_hash,
            raw_storage_key=f"sha256/{content_hash[:2]}/{content_hash}.html",
            raw_payload={
                "source_format": "rudn_ssr",
                "campaign_year": self.campaign_year,
                "group_id": self.group_id,
                "title": self.title,
                "condition": self.condition,
                "financing": self.financing,
                "count": len(applications),
                "parser_version": self.parser_version,
                "source_hash": content_hash,
            },
            parser_version=self.parser_version,
        )
        return ParserResult(ParserResultStatus.VALID, snapshot, (), ())


def _title_from_page(html: str) -> str | None:
    text = unescape(re.sub(r"<[^>]+>", "\n", html))
    text = re.sub(r"[ \t\xa0]+", " ", text)
    match = re.search(r"Специальность\s*\n?\s*([^\n]{3,60})", text)
    if match:
        value = match.group(1).strip()
        match_group = re.search(r"Конкурсная группа\s*\n?\s*([^\n]{2,50})", text)
        if match_group:
            return f"{value} — {match_group.group(1).strip()}"
        return value
    return None


def _seat_from_page(html: str) -> int | None:
    text = unescape(re.sub(r"<[^>]+>", " ", html))
    match = re.search(r"(\d+)\s+мест", text)
    return int(match.group(1)) if match else None
