from __future__ import annotations

from dataclasses import dataclass
from typing import Any

ENGINE_VERSION = "deterministic-1"


@dataclass(frozen=True)
class GlobalEventSummary:
    counts_by_condition: dict[str, dict[str, int]]


@dataclass(frozen=True)
class LocalTargetSignals:
    rank_trend: float = 0.0
    nearby_rank_volatility: float = 0.0
    nearby_consent_changes: int = 0
    threshold_turbulence: float = 0.0
    recent_appeared_near_target: int = 0
    recent_disappeared_near_target: int = 0


@dataclass(frozen=True)
class ForecastInput:
    campaign_year: int
    identity_namespace: str
    current_snapshot_id: str
    applicant_uid_hmac: str
    admission_condition: str
    rank: int | None
    competitive_score: float | None
    enrollment_priority: int | None
    consent: bool | None
    application_status: str | None
    bvi: bool
    advantages: bool | None
    seat_count: int | None
    data_complete: bool
    global_event_summary: GlobalEventSummary
    local_target_signals: LocalTargetSignals


@dataclass(frozen=True)
class ForecastOutput:
    probability_low: float
    probability_high: float
    estimated_rank_min: int | None
    estimated_rank_max: int | None
    confidence: str
    explanation: dict[str, Any]
    engine_version: str = ENGINE_VERSION


class AdmissionProbabilityEngine:
    def calculate(self, value: ForecastInput) -> ForecastOutput:
        self._validate(value)
        signals: dict[str, Any] = {
            "rank_vs_seat_count": "unknown",
            "consent": value.consent,
            "admission_condition": value.admission_condition,
            "bvi": value.bvi,
            "data_complete": value.data_complete,
        }
        assumptions: list[str] = []
        if value.rank is None:
            base = 0.5
            width = 0.45
            assumptions.append("rank_missing")
        elif value.seat_count is None or value.seat_count <= 0:
            base = 0.5
            width = 0.4
            assumptions.append("seat_count_unknown")
        else:
            margin = (value.seat_count - value.rank) / value.seat_count
            base = _clamp(0.5 + 0.8 * margin, 0.05, 0.95)
            width = 0.12
            signals["rank_vs_seat_count"] = round(value.rank / value.seat_count, 4)

        if value.consent is True:
            base += 0.08
        elif value.consent is False:
            base -= 0.08
        else:
            width += 0.06
            assumptions.append("consent_unknown")

        if value.bvi:
            base += 0.04
        if value.admission_condition != "general_competition":
            width += 0.03
            assumptions.append("condition_specific_seat_semantics")

        # Score and priority are intentionally bounded weak modifiers.
        score_modifier = _clamp(((value.competitive_score or 200) - 200) / 1000, -0.03, 0.03)
        priority_modifier = _clamp(((10 - (value.enrollment_priority or 10)) / 1000), -0.01, 0.01)
        base += score_modifier + priority_modifier

        local = value.local_target_signals
        base += _clamp(-local.rank_trend / 100, -0.06, 0.06)
        base += _clamp(
            (local.recent_disappeared_near_target - local.recent_appeared_near_target) / 100,
            -0.04,
            0.04,
        )
        width += _clamp(local.nearby_rank_volatility / 100, 0, 0.12)
        width += _clamp(local.threshold_turbulence / 100, 0, 0.12)
        width += _clamp(local.nearby_consent_changes / 100, 0, 0.08)
        if not value.data_complete:
            width += 0.1
            assumptions.append("incomplete_data")

        low = _clamp(base - width, 0.0, 1.0)
        high = _clamp(base + width, 0.0, 1.0)
        confidence = "high" if width <= 0.18 and value.data_complete else "medium"
        if width > 0.35:
            confidence = "low"
        if value.rank is None and value.seat_count is None:
            confidence = "unknown"
        explanation = {
            "signals": signals,
            "event_adjustments": {
                "global": value.global_event_summary.counts_by_condition.get(
                    value.admission_condition, {}
                ),
                "local": {
                    "rank_trend": local.rank_trend,
                    "nearby_rank_volatility": local.nearby_rank_volatility,
                    "nearby_consent_changes": local.nearby_consent_changes,
                    "threshold_turbulence": local.threshold_turbulence,
                    "recent_appeared_near_target": local.recent_appeared_near_target,
                    "recent_disappeared_near_target": local.recent_disappeared_near_target,
                },
            },
            "assumptions": assumptions,
            "limitations": ["heuristic_no_training", "not_an_ai_model", "not_a_guarantee"],
        }
        return ForecastOutput(
            probability_low=round(low, 4),
            probability_high=round(high, 4),
            estimated_rank_min=value.rank,
            estimated_rank_max=value.rank,
            confidence=confidence,
            explanation=explanation,
        )

    @staticmethod
    def _validate(value: ForecastInput) -> None:
        if not value.identity_namespace or not value.current_snapshot_id:
            raise ValueError("forecast identity is incomplete")
        if value.rank is not None and value.rank <= 0:
            raise ValueError("rank must be positive")
        if value.seat_count is not None and value.seat_count < 0:
            raise ValueError("seat count must be non-negative")
        if value.competitive_score is not None and not 0 <= value.competitive_score <= 400:
            raise ValueError("score out of range")


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
