from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from packages.diff import EVENT_TYPES
from packages.forecasting.engine import GlobalEventSummary, LocalTargetSignals


def extract_global_event_summary(
    events: Iterable[tuple[str, str | None]],
) -> GlobalEventSummary:
    result: dict[str, Counter[str]] = {}
    for event_type, condition in events:
        if event_type not in EVENT_TYPES:
            continue
        result.setdefault(condition or "unknown", Counter())[event_type] += 1
    return GlobalEventSummary({condition: dict(counts) for condition, counts in result.items()})


def extract_local_target_signals(
    *, rank_trend: float = 0.0, nearby_rank_volatility: float = 0.0,
    nearby_consent_changes: int = 0, threshold_turbulence: float = 0.0,
    recent_appeared_near_target: int = 0, recent_disappeared_near_target: int = 0,
) -> LocalTargetSignals:
    return LocalTargetSignals(
        rank_trend=rank_trend,
        nearby_rank_volatility=nearby_rank_volatility,
        nearby_consent_changes=nearby_consent_changes,
        threshold_turbulence=threshold_turbulence,
        recent_appeared_near_target=recent_appeared_near_target,
        recent_disappeared_near_target=recent_disappeared_near_target,
    )
