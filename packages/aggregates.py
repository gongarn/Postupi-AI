from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

DATA_FILE = Path("data") / "aggregates_2026.csv"

UNIVERSITY_NAMES = {
    "fa": "Финансовый университет",
    "itmo": "ИТМО",
    "misis": "НИТУ МИСИС",
    "mpei": "НИУ МЭИ",
    "msu": "МГУ им. М.В. Ломоносова",
    "rnimu": "РНИМУ им. Н.И. Пирогова",
    "rudn": "РУДН",
    "sechenov": "Первый МГМУ им. И.М. Сеченова",
    "stankin": "МГТУ СТАНКИН",
}


def group_id(university: str, group_title: str) -> str:
    import hashlib

    return hashlib.sha1(f"{university}:{group_title}".encode()).hexdigest()[:12]


@dataclass(frozen=True)
class GroupAggregate:
    university: str
    group_title: str
    campaign_year: int
    snapshot_date: str
    applications: int
    seat_counts: str
    min_enrolled_score: float | None
    last_rank: int | None

    @property
    def university_name(self) -> str:
        return UNIVERSITY_NAMES.get(self.university, self.university)

    @property
    def id(self) -> str:
        return group_id(self.university, self.group_title)

    @property
    def seats_display(self) -> str:
        import re

        seats = re.findall(r'"([a-z_]+)":\s*(\d+)', self.seat_counts)
        parts = [f"{key}: {value}" for key, value in seats if key == "general_competition"]
        return parts[0] if parts else "—"

    @property
    def score_display(self) -> str:
        if self.min_enrolled_score is None:
            return "—"
        return f"{self.min_enrolled_score:g}"


def load_groups(path: Path = DATA_FILE) -> list[GroupAggregate]:
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        groups: list[GroupAggregate] = []
        for row in reader:
            try:
                groups.append(
                    GroupAggregate(
                        university=row["university"],
                        group_title=row["group_title"],
                        campaign_year=int(row["campaign_year"]),
                        snapshot_date=row["snapshot_date"],
                        applications=int(row["applications"] or 0),
                        seat_counts=row["seat_counts"],
                        min_enrolled_score=(
                            float(row["min_enrolled_score"])
                            if row["min_enrolled_score"]
                            else None
                        ),
                        last_rank=(
                            int(row["last_rank"]) if row["last_rank"] else None
                        ),
                    )
                )
            except (ValueError, KeyError):
                continue
        return groups


def groups_by_university(groups: list[GroupAggregate]) -> dict[str, list[GroupAggregate]]:
    by_university: dict[str, list[GroupAggregate]] = {}
    for group in groups:
        by_university.setdefault(group.university, []).append(group)
    for items in by_university.values():
        items.sort(key=lambda item: (item.min_enrolled_score is None, item.group_title))
    return by_university


def search_groups(groups: list[GroupAggregate], query: str) -> list[GroupAggregate]:
    query = query.strip().lower()
    if not query:
        return groups
    return [
        group
        for group in groups
        if query in group.group_title.lower()
        or query in group.university_name.lower()
        or query in group.university.lower()
    ]
