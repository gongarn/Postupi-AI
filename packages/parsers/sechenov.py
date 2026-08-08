from __future__ import annotations

import hashlib
import re
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
from packages.parsers.html_tables import cell_text

SECHENOV_NAMESPACE = "admissions_uid:sechenov:{campaign_year}:v1"


class SechenovParser(BaseUniversityParser):
    """Парсер AJAX-фрагмента конкурсного списка Сеченовского университета.

    Bitrix-эндпоинт applications.php?COMPETITIVE_GROUP_ID=N возвращает таблицу
    с № и УИД абитуриента (анонимизировано). Других полей в публичном
    виджете нет — snapshot пригоден для мониторинга и diff, но не для
    прогноза (нет баллов/согласий).
    """

    parser_version = "sechenov-grid-1"

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
        self.identity_namespace = SECHENOV_NAMESPACE.format(campaign_year=campaign_year)

    def parse(self, content: bytes, *, source_url: str, fetched_at: datetime) -> ParserResult:
        try:
            html = content.decode("utf-8", errors="replace")
        except Exception as exc:  # pragma: no cover
            return ParserResult(ParserResultStatus.FAILED, None, (str(exc),), ())
        rows = _extract_data_rows(html)
        applications = [
            NormalizedApplication(
                applicant_uid_hmac=hash_uid(
                    secret=self.uid_secret,
                    identity_namespace=self.identity_namespace,
                    uid=uid,
                ),
                identity_namespace=self.identity_namespace,
                admission_condition="general_competition",
                rank=index + 1,
                enrollment_priority=None,
                competitive_score=None,
                application_status=None,
                consent=None,
                raw_payload={},
            )
            for index, uid in enumerate(rows)
        ]
        if not applications:
            return ParserResult(ParserResultStatus.FAILED, None, ("no applications",), ())
        content_hash = hashlib.sha256(content).hexdigest()
        snapshot = ParsedSnapshot(
            group=NormalizedCompetitionGroup(
                university_code="sechenov",
                university_name="Первый МГМУ им. И.М. Сеченова",
                campaign_year=self.campaign_year,
                external_group_id=self.group_id,
                title=self.title,
                degree="bachelor",
                financing="budget",
                identity_namespace=self.identity_namespace,
                priority_kind="unknown",
                priority_confidence="unknown",
                source_metadata={"source_format": "sechenov_grid", "count": len(applications)},
            ),
            applications=tuple(applications),
            source_url=source_url,
            fetched_at=fetched_at,
            content_hash=content_hash,
            raw_storage_key=f"sha256/{content_hash[:2]}/{content_hash}.html",
            raw_payload={
                "source_format": "sechenov_grid",
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


def _cell(row: list[str], index: int) -> str | None:
    if index >= len(row):
        return None
    return row[index] or None


def _extract_data_rows(html: str) -> list[str]:
    """Сеченовский виджет использует вложенные таблицы; извлекаем строки
    напрямую: вторая ячейка — УИД абитуриента (7 цифр)."""
    uids: list[str] = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        cells = [
            cell_text(cell)
            for cell in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)
        ]
        if len(cells) < 2:
            continue
        uid = cells[1]
        if re.fullmatch(r"\d{6,8}", uid):
            uids.append(uid)
    return uids
