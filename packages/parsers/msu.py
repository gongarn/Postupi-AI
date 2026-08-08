from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
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
    map_condition,
    to_float,
    to_int,
)

MSU_NAMESPACE = "admissions_uid:msu:{campaign_year}:v1"


@dataclass(frozen=True)
class MsuSection:
    anchor_id: str
    program: str
    condition: str
    seat_count: int | None
    html: str


def split_sections(page_html: str) -> list[MsuSection]:
    """Разбивает страницу факультета МГУ на конкурсные секции.

    Секция = <h4 id="..."> (якорь конкурса), внутри div.rating-concourse:
    [h4.rating-concourse-title — условие] [Вид мест / Всего мест /
    Список сформирован] <table>. Программа берётся из текста
    «Образовательная программа: …» или из предыдущего h4-заголовка.
    """
    heading_pattern = re.compile(r"<h4([^>]*)>(.*?)</h4>", re.S)
    headings = list(heading_pattern.finditer(page_html))
    anchored: list[tuple[int, str, str, bool]] = []
    for _, match in enumerate(headings):
        attrs, body = match.group(1), match.group(2)
        anchor_match = re.search(r'id="([^"]+)"', attrs)
        if not anchor_match:
            continue
        is_condition = "rating-concourse-title" in attrs
        text = unescape(re.sub(r"<[^>]+>", "", body)).strip()
        anchored.append((match.start(), anchor_match.group(1), text, is_condition))
    sections: list[MsuSection] = []
    last_program = "unknown"
    for index, (position, anchor_id, heading_text, is_condition) in enumerate(anchored):
        end = anchored[index + 1][0] if index + 1 < len(anchored) else len(page_html)
        block = page_html[position:end]
        if not is_condition:
            last_program = heading_text
        seat_match = re.search(r"Всего мест[:：]\s*(\d+)", block)
        program_match = re.search(r"Образовательная программа[:：]\s*([^<]+)", block)
        condition_text = heading_text if is_condition else ""
        sections.append(
            MsuSection(
                anchor_id=anchor_id,
                program=(
                    unescape(program_match.group(1)).strip()
                    if program_match
                    else last_program
                ),
                condition=map_condition(condition_text),
                seat_count=int(seat_match.group(1)) if seat_match else None,
                html=block,
            )
        )
    return sections




class MsuSectionParser(BaseUniversityParser):
    """Парсер одной секции (программа × условие) конкурсного списка МГУ.

    В данных — «Код абитуриента ЕПГУ» (анонимизировано вузом), приоритет,
    ОВП/ВПП, согласие, баллы, статус заявления.
    """

    parser_version = "msu-section-1"

    def __init__(
        self,
        *,
        uid_secret: str,
        campaign_year: int = 2026,
        section: MsuSection | None = None,
        faculty_code: str = "dep",
    ) -> None:
        self.uid_secret = uid_secret
        self.campaign_year = campaign_year
        self.section = section
        self.faculty_code = faculty_code
        self.identity_namespace = MSU_NAMESPACE.format(campaign_year=campaign_year)

    def parse(self, content: bytes, *, source_url: str, fetched_at: datetime) -> ParserResult:
        try:
            html = content.decode("utf-8", errors="replace")
        except Exception as exc:  # pragma: no cover
            return ParserResult(ParserResultStatus.FAILED, None, (str(exc),), ())
        section = self.section or _section_from_html(html)
        tables = extract_tables(html)
        if not tables:
            return ParserResult(ParserResultStatus.FAILED, None, ("no tables",), ())
        data_table = next(
            (t for t in tables if any(_looks_like_msu_data(row) for row in t)),
            None,
        )
        if data_table is None:
            return ParserResult(ParserResultStatus.FAILED, None, ("no data rows",), ())
        rows = [row for row in data_table if _looks_like_msu_data(row)]
        applications: list[NormalizedApplication] = []
        for index, row in enumerate(rows):
            code = _msu_code(row[1] if len(row) > 1 else None)
            if not code or len(row) < 10:
                continue
            applications.append(
                NormalizedApplication(
                    applicant_uid_hmac=hash_uid(
                        secret=self.uid_secret,
                        identity_namespace=self.identity_namespace,
                        uid=code,
                    ),
                    identity_namespace=self.identity_namespace,
                    admission_condition=section.condition,
                    rank=index + 1,
                    enrollment_priority=to_int(_cell(row, 2)),
                    competitive_score=to_float(_cell(row, 6)),
                    application_status=_cell(row, len(row) - 1),
                    consent=_consent_ru(_cell(row, len(row) - 4)),
                    raw_payload={
                        "ovp": _cell(row, 3),
                        "vpp": _cell(row, 4),
                        "order_number": _cell(row, 5),
                        "score_vi": to_float(_cell(row, 7)),
                        "ia": to_float(_cell(row, 8)),
                        "dorm": _cell(row, len(row) - 2),
                        "advantage": _cell(row, len(row) - 3),
                    },
                )
            )
        if not applications:
            return ParserResult(ParserResultStatus.FAILED, None, ("no applications",), ())
        content_hash = hashlib.sha256(content).hexdigest()
        snapshot = ParsedSnapshot(
            group=NormalizedCompetitionGroup(
                university_code="msu",
                university_name="МГУ им. М.В. Ломоносова",
                campaign_year=self.campaign_year,
                external_group_id=f"{self.faculty_code}:{section.anchor_id}",
                title=f"{section.program} ({section.condition})",
                degree="bachelor",
                financing="budget",
                identity_namespace=self.identity_namespace,
                priority_kind="university_enrollment",
                priority_confidence="strong",
                seat_counts={section.condition: section.seat_count},
                source_metadata={"source_format": "msu_section", "count": len(applications)},
            ),
            applications=tuple(applications),
            source_url=source_url,
            fetched_at=fetched_at,
            content_hash=content_hash,
            raw_storage_key=f"sha256/{content_hash[:2]}/{content_hash}.html",
            raw_payload={
                "source_format": "msu_section",
                "campaign_year": self.campaign_year,
                "faculty": self.faculty_code,
                "anchor": section.anchor_id,
                "program": section.program,
                "condition": section.condition,
                "seat_count": section.seat_count,
                "count": len(applications),
                "parser_version": self.parser_version,
                "source_hash": content_hash,
            },
            parser_version=self.parser_version,
        )
        return ParserResult(ParserResultStatus.VALID, snapshot, (), ())


def _section_from_html(html: str) -> MsuSection:
    sections = split_sections(html)
    if sections:
        return sections[0]
    return MsuSection("sec", "unknown", "general_competition", None, html)


def _cell(row: list[str], index: int) -> str | None:
    if index >= len(row):
        return None
    return row[index] or None


def _looks_like_msu_data(row: list[str]) -> bool:
    return bool(row and (row[0].isdigit() or re.fullmatch(r"\d{6,8}( \d+)?", row[1] or "")))


def _msu_code(value: str | None) -> str | None:
    """Код ЕПГУ вида «1166417 022102053908» — берём первое число."""
    if value is None:
        return None
    match = re.search(r"\d{6,8}", value)
    return match.group() if match else None


def _consent_ru(value: str | None) -> bool | None:
    if value is None:
        return None
    lowered = value.lower().strip()
    if lowered in {"да", "yes", "+", "✓", "1"}:
        return True
    if lowered in {"нет", "no", "-", "0", "—"}:
        return False
    return None
