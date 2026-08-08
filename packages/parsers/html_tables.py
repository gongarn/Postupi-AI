from __future__ import annotations

import re
from html import unescape

_CONDITION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"особая квота", re.I), "by_special_quota"),
    (re.compile(r"отдельная квота", re.I), "by_unusual_quota"),
    (re.compile(r"целевая квота|целевому конкурсу|целевой конкурс", re.I), "by_target_quota"),
    (re.compile(r"бви|без вступительных|без вст\. испытаний", re.I), "without_entry_tests"),
    (re.compile(r"договор|платн|внебюджет", re.I), "paid_competition"),
)


def map_condition(text: str | None) -> str:
    if not text:
        return "general_competition"
    for pattern, condition in _CONDITION_PATTERNS:
        if pattern.search(text):
            return condition
    return "general_competition"


def cell_text(cell: str) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", cell)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return unescape(cleaned).strip()


def extract_rows(table: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.S):
        cells = [cell_text(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)]
        if cells:
            rows.append(cells)
    return rows


def extract_tables(html: str) -> list[list[list[str]]]:
    return [extract_rows(table) for table in re.findall(r"<table.*?</table>", html, re.S)]


def to_int(value: str | None) -> int | None:
    if value is None:
        return None
    match = re.search(r"-?\d+", value.replace("\u00a0", " "))
    return int(match.group()) if match else None


def to_float(value: str | None) -> float | None:
    if value is None:
        return None
    match = re.search(r"-?\d+(?:[.,]\d+)?", value.replace("\u00a0", " "))
    return float(match.group().replace(",", ".")) if match else None


def yes_no(value: str | None) -> bool | None:
    if value is None:
        return None
    if re.search(r"\b(да|yes|+\s*|\u2713|✓)\b", value, re.I):
        return True
    if re.search(r"\b(нет|no|-)\b", value, re.I):
        return False
    return None


_HEADER_SYNONYMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("code", ("код", "уид", "уи", "уникальный")),
    ("rank", ("№ п/п", "№", "порядковый")),
    ("ovp", ("основной высший",)),
    ("vpp", ("высший проходной",)),
    ("priority", ("приоритет",)),
    ("consent", ("согласие",)),
    ("status", ("статус", "примечание")),
    ("score_no_ia", ("без ид",)),
    ("score", ("сумма",)),
    ("ia", ("индивидуальн", "баллы ид", "за ид", "ид")),
    ("ia_extra", ("ид доп",)),
    ("financing", ("финансирование", "основа")),
    ("faculty", ("факультет",)),
    ("group", ("группа", "направление")),
    ("contest", ("вид конкурса",)),
    ("dorm", ("общежит",)),
    ("contract", ("договор",)),
    ("advantage", ("преимущ",)),
    ("enrolled", ("зачислен",)),
)


def header_map(rows: list[list[str]]) -> tuple[dict[str, int], list[list[str]]]:
    """Находит строку заголовка по ключевым словам и возвращает
    (синоним → индекс) и строки данных."""
    header_index = 0
    for index, row in enumerate(rows):
        text = " ".join(row).lower()
        if len(row) >= 4 and ("код" in text or "сумма" in text or "№" in text):
            header_index = index
            break
    header = rows[header_index]
    mapping: dict[str, int] = {}
    for cell_index, cell in enumerate(header):
        key = cell.lower()
        for synonym, needles in _HEADER_SYNONYMS:
            if any(needle in key for needle in needles):
                mapping[synonym] = cell_index
                break
    data: list[list[str]] = []
    for row in rows[header_index + 1:]:
        if len(row) < 2:
            continue
        if row[0].isdigit() or (len(row) > 1 and re.fullmatch(r"\d{6,8}( \d+)?", row[1] or "")):
            data.append(row)
    return mapping, data
