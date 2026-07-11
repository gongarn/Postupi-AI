from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TrackView:
    target_id: str
    university_name: str
    external_group_id: str
    campaign_year: int
    title: str
    snapshot_status: str
    probability_low: float | None
    probability_high: float | None
    confidence: str | None
    event_counts: dict[str, int]
    explanation: dict[str, Any] | None


def start_text() -> str:
    return (
        "Postupi AI помогает смотреть сохранённые направления и "
        "детерминированный ориентировочный прогноз.\n\n"
        "Приватность: бот не показывает исходные идентификаторы, персональные данные "
        "или внутренние данные других пользователей.\n\n"
        "Прогноз не является гарантией зачисления."
    )


def help_text() -> str:
    return (
        "/start — описание бота\n"
        "/tracks — мои направления\n"
        "/help — эта справка\n\n"
        "Сейчас доступны только сохранённые направления ITMO и текущие snapshots. "
        "Автоматического мониторинга, уведомлений и cross-university matching нет.\n\n"
        "Вероятность является детерминированной оценкой, а не гарантией зачисления."
    )


def empty_tracks_text() -> str:
    return "Сохранённых направлений пока нет."


def tracks_text(views: list[TrackView]) -> str:
    lines = ["Мои направления:"]
    for index, view in enumerate(views, start=1):
        probability = _probability(view)
        lines.append(
            f"{index}. {view.university_name}, группа {view.external_group_id}, "
            f"кампания {view.campaign_year}\n"
            f"   {view.title}\n"
            f"   snapshot: {view.snapshot_status}; вероятность: {probability}"
        )
    return "\n".join(lines)


def track_detail_text(view: TrackView) -> str:
    lines = [
        f"{view.university_name}: {view.title}",
        f"Группа: {view.external_group_id}; кампания: {view.campaign_year}",
        f"Текущий snapshot: {view.snapshot_status}",
        f"Вероятность: {_probability(view)}",
        f"Уверенность: {view.confidence or 'unknown'}",
        "",
        "Последние изменения:",
        _event_summary(view.event_counts),
    ]
    if view.explanation:
        lines.extend(
            [
                "",
                "Сигналы:",
                _values(view.explanation.get("signals")),
                "Допущения:",
                _values(view.explanation.get("assumptions")),
                "Ограничения:",
                _values(view.explanation.get("limitations")),
            ]
        )
    return "\n".join(lines)


def _probability(view: TrackView) -> str:
    if view.probability_low is None or view.probability_high is None:
        return "нет оценки"
    return f"{view.probability_low:.0%}–{view.probability_high:.0%}"


def _event_summary(counts: dict[str, int]) -> str:
    if not counts:
        return "Нет новых изменений."
    return ", ".join(f"{key}: {value}" for key, value in sorted(counts.items()))


def _values(value: Any) -> str:
    if value is None:
        return "нет данных"
    if isinstance(value, dict):
        return ", ".join(f"{key}={item}" for key, item in sorted(value.items())) or "нет данных"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) or "нет данных"
    return str(value)
