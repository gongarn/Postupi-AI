from uuid import uuid4

import pytest

from packages.forecasting.engine import (
    AdmissionProbabilityEngine,
    CandidateCohort,
    ForecastInput,
    GlobalEventSummary,
    LocalTargetSignals,
    ProbabilisticAdmissionEngine,
    RetentionCalibration,
)


def _input(**changes: object) -> ForecastInput:
    values: dict[str, object] = {
        "campaign_year": 2025,
        "identity_namespace": "test:2025",
        "current_snapshot_id": str(uuid4()),
        "applicant_uid_hmac": "hmac-fingerprint-only",
        "admission_condition": "general_competition",
        "rank": 10,
        "competitive_score": 250.0,
        "enrollment_priority": 1,
        "consent": True,
        "application_status": "recommended",
        "bvi": False,
        "advantages": False,
        "seat_count": 20,
        "data_complete": True,
        "global_event_summary": GlobalEventSummary({}),
        "local_target_signals": LocalTargetSignals(),
    }
    values.update(changes)
    return ForecastInput(**values)


def test_engine_produces_explanation_without_uid() -> None:
    output = AdmissionProbabilityEngine().calculate(_input())
    serialized = str(output.explanation)
    assert 0 <= output.probability_low <= output.probability_high <= 1
    assert "hmac-fingerprint-only" not in serialized
    assert "raw_uid" not in serialized
    assert output.engine_version == "deterministic-1"


def test_probability_is_monotonic_for_rank_and_seats() -> None:
    engine = AdmissionProbabilityEngine()
    better_rank = engine.calculate(_input(rank=5))
    worse_rank = engine.calculate(_input(rank=25))
    more_seats = engine.calculate(_input(seat_count=40))
    assert better_rank.probability_low > worse_rank.probability_low
    assert more_seats.probability_low > worse_rank.probability_low


def test_score_and_priority_are_weak_modifiers() -> None:
    engine = AdmissionProbabilityEngine()
    low = engine.calculate(_input(competitive_score=0, enrollment_priority=100))
    high = engine.calculate(_input(competitive_score=400, enrollment_priority=1))
    assert high.probability_low - low.probability_low <= 0.08


def test_uncertain_input_returns_wide_low_confidence_interval() -> None:
    output = AdmissionProbabilityEngine().calculate(
        _input(rank=None, seat_count=None, consent=None, data_complete=False)
    )
    assert output.confidence == "unknown"
    assert output.probability_high - output.probability_low >= 0.7


def test_invalid_input_is_rejected() -> None:
    with pytest.raises(ValueError, match="score out of range"):
        AdmissionProbabilityEngine().calculate(_input(competitive_score=401))


def test_probabilistic_engine_is_reproducible_and_identity_safe() -> None:
    value = _input(
        retention_calibration=RetentionCalibration(
            retained=140, observations=200, snapshot_count=3
        ),
        candidate_cohorts=(
            CandidateCohort(count=5, stay_adjustment=0.12),
            CandidateCohort(count=8, stay_adjustment=-0.18),
        ),
    )
    first = ProbabilisticAdmissionEngine().calculate(value)
    second = ProbabilisticAdmissionEngine().calculate(value)

    assert first == second
    assert first.engine_version == "probabilistic-2"
    assert 0 <= first.probability_low <= first.probability_high <= 1
    assert "hmac-fingerprint-only" not in str(first.explanation)


def test_probabilistic_engine_requires_three_snapshots() -> None:
    value = _input(
        retention_calibration=RetentionCalibration(retained=1, observations=2, snapshot_count=2)
    )
    with pytest.raises(ValueError, match="three snapshots"):
        ProbabilisticAdmissionEngine().calculate(value)
