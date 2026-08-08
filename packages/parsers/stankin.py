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
from packages.parsers.html_tables import map_condition, to_float, to_int

STANKIN_NAMESPACE = "admissions_uid:stankin:{campaign_year}:v1"

# Колонки Bitrix-грида (проверено по настройкам грида 08.08.2026).
_COLUMNS = {
    "code": "PROPERTY_423",
    "priority": "PROPERTY_709",
    "vpp": "PROPERTY_710",
    "ovp": "PROPERTY_711",
    "consent": "PROPERTY_400",
    "dorm": "PROPERTY_401",
    "status": "PROPERTY_419",
    "contract": "PROPERTY_770",
    "score": "PROPERTY_379",
    "ia": "PROPERTY_380",
    "score_no_ia": "PROPERTY_769",
    "advantage_9": "PROPERTY_767",
    "advantage_10": "PROPERTY_768",
    "financing": "PROPERTY_388",
    "profile_subject": "PROPERTY_399",
}


class StankinParser(BaseUniversityParser):
    """Парсер Bitrix-грида конкурсных списков МГТУ СТАНКИН.

    Данные анонимизированы («Уникальный код»), есть приоритеты, согласия,
    баллы, статусы. Группа определяется направлением и основой финансирования
    (параметры PROPERTY_* в URL грида).
    """

    parser_version = "stankin-grid-2"

    def __init__(
        self,
        *,
        uid_secret: str,
        campaign_year: int = 2026,
        group_id: str | None = None,
        title: str | None = None,
        financing: str = "budget",
    ) -> None:
        self.uid_secret = uid_secret
        self.campaign_year = campaign_year
        self.group_id = group_id or "unknown"
        self.title = title or group_id or "unknown"
        self.financing = financing
        self.identity_namespace = STANKIN_NAMESPACE.format(campaign_year=campaign_year)

    def parse(self, content: bytes, *, source_url: str, fetched_at: datetime) -> ParserResult:
        try:
            html = content.decode("utf-8", errors="replace")
        except Exception as exc:  # pragma: no cover
            return ParserResult(ParserResultStatus.FAILED, None, (str(exc),), ())
        rows = _grid_rows(html)
        if not rows:
            return ParserResult(ParserResultStatus.FAILED, None, ("no grid rows",), ())
        applications: list[NormalizedApplication] = []
        seen_uids: set[str] = set()
        for row in rows:
            code = row.get("code")
            if not code or code in seen_uids:
                continue
            seen_uids.add(code)
            applications.append(
                NormalizedApplication(
                    applicant_uid_hmac=hash_uid(
                        secret=self.uid_secret,
                        identity_namespace=self.identity_namespace,
                        uid=code,
                    ),
                    identity_namespace=self.identity_namespace,
                    admission_condition=map_condition(self.title),
                    bvi=_is_bvi(row.get("profile_subject")),
                    rank=len(applications) + 1,
                    enrollment_priority=to_int(row.get("priority")),
                    competitive_score=to_float(row.get("score")),
                    application_status=row.get("status"),
                    consent=_consent(row.get("consent")),
                    raw_payload={
                        "score_without_ia": to_float(row.get("score_no_ia")),
                        "ia": to_float(row.get("ia")),
                        "contract": row.get("contract"),
                        "dorm": row.get("dorm"),
                        "ovp": row.get("ovp"),
                        "vpp": row.get("vpp"),
                        "advantage_9": row.get("advantage_9"),
                        "advantage_10": row.get("advantage_10"),
                    },
                )
            )
        if not applications:
            return ParserResult(ParserResultStatus.FAILED, None, ("no applications",), ())
        content_hash = hashlib.sha256(content).hexdigest()
        snapshot = ParsedSnapshot(
            group=NormalizedCompetitionGroup(
                university_code="stankin",
                university_name="МГТУ СТАНКИН",
                campaign_year=self.campaign_year,
                external_group_id=self.group_id,
                title=self.title,
                degree="bachelor",
                financing=self.financing,
                identity_namespace=self.identity_namespace,
                priority_kind="university_enrollment",
                priority_confidence="strong",
                source_metadata={"source_format": "stankin_grid", "count": len(applications)},
            ),
            applications=tuple(applications),
            source_url=source_url,
            fetched_at=fetched_at,
            content_hash=content_hash,
            raw_storage_key=f"sha256/{content_hash[:2]}/{content_hash}.html",
            raw_payload={
                "source_format": "stankin_grid",
                "campaign_year": self.campaign_year,
                "group_id": self.group_id,
                "title": self.title,
                "financing": self.financing,
                "count": len(applications),
                "parser_version": self.parser_version,
                "source_hash": content_hash,
            },
            parser_version=self.parser_version,
        )
        return ParserResult(ParserResultStatus.VALID, snapshot, (), ())


def _grid_rows(html: str) -> list[dict[str, str | None]]:
    """Извлекает строки грида: ячейки с data-column-id → текст значения."""
    rows: list[dict[str, str | None]] = []
    alias = {column_id: key for key, column_id in _COLUMNS.items()}
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        cells: dict[str, str | None] = {}
        for cell in re.findall(
            r"<td[^>]*data-column-id=\"([^\"]+)\"[^>]*>(.*?)</td>", row_html, re.S
        ):
            column_id, body = cell
            value = unescape(re.sub(r"<[^>]+>", " ", body))
            value = re.sub(r"\s+", " ", value).strip()
            key = alias.get(column_id)
            if key:
                cells[key] = value or None
        if "code" in cells:
            rows.append(cells)
    return rows


def _consent(value: str | None) -> bool | None:
    if value is None:
        return None
    if value in {"✓", "Да", "да", "1", "+", "Есть"}:
        return True
    if value in {"Нет", "нет", "0", "-", "—"}:
        return False
    return None


def _is_bvi(profile_subject: str | None) -> bool | None:
    if profile_subject is None:
        return None
    return profile_subject in {"", "0", "0.0", "—", "-"}
