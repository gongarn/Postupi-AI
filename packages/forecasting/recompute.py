from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select

from packages.forecasting.engine import (
    AdmissionProbabilityEngine,
    CandidateCohort,
    ForecastInput,
    GlobalEventSummary,
    LocalTargetSignals,
    ProbabilisticAdmissionEngine,
    RetentionCalibration,
)
from packages.forecasting.persistence import persist_forecast
from packages.persistence.models import (
    Application,
    CompetitionGroup,
    Confidence,
    ListSnapshot,
    PriorityKind,
    SnapshotStatus,
    University,
    UserTarget,
)
from packages.persistence.uow import UnitOfWork


@dataclass(frozen=True)
class ForecastRecomputeOutcome:
    created: int = 0
    skipped: int = 0
    reason: str | None = None


async def recompute_probabilistic_forecasts(
    uow: UnitOfWork, *, current_snapshot_id: UUID
) -> ForecastRecomputeOutcome:
    snapshot = await uow.session.get(ListSnapshot, current_snapshot_id)
    if snapshot is None or snapshot.status != SnapshotStatus.VALID:
        return ForecastRecomputeOutcome(reason="snapshot_unavailable")
    group, university = (
        await uow.session.execute(
            select(CompetitionGroup, University)
            .join(University, University.id == CompetitionGroup.university_id)
            .where(CompetitionGroup.id == snapshot.competition_group_id)
        )
    ).one()
    if university.code != "itmo":
        return ForecastRecomputeOutcome(reason="university_not_eligible")

    coverage = await _university_coverage(uow, group, snapshot)
    if not coverage.complete:
        return ForecastRecomputeOutcome(reason="university_coverage_incomplete")
    if group.priority_kind != PriorityKind.UNIVERSITY_ENROLLMENT:
        return ForecastRecomputeOutcome(reason="university_priority_unverified")
    if group.priority_confidence not in (Confidence.VERIFIED, Confidence.STRONG):
        return ForecastRecomputeOutcome(reason="university_priority_unverified")

    history = await _history_to_snapshot(uow, snapshot)
    if len(history) < 3:
        return ForecastRecomputeOutcome(reason="insufficient_snapshots")
    targets = list(
        (
            await uow.session.scalars(
                select(UserTarget).where(UserTarget.competition_group_id == group.id)
            )
        ).all()
    )
    if not targets:
        return ForecastRecomputeOutcome(reason="no_targets")

    applications = await _applications_for_snapshots(uow, [item.id for item in history])
    current_applications = applications[snapshot.id]
    batch_applications = await _applications_for_snapshots(
        uow, [item.id for item in coverage.snapshots_by_group.values()]
    )
    applications_by_uid = _applications_by_uid(batch_applications.values())
    calibration_by_condition = _calibrations(history, applications)
    created = 0
    skipped = 0
    for target in targets:
        application = _target_application(current_applications, target)
        if application is None:
            skipped += 1
            continue
        seat_count = _seat_count(snapshot, application.admission_condition)
        calibration = calibration_by_condition.get(application.admission_condition)
        if seat_count is None or calibration is None:
            skipped += 1
            continue
        cohorts, cross_group_excluded = _candidate_cohorts(
            current_applications, application, applications_by_uid
        )
        value = ForecastInput(
            campaign_year=snapshot.campaign_year,
            identity_namespace=target.identity_namespace,
            current_snapshot_id=str(snapshot.id),
            applicant_uid_hmac=target.applicant_uid_hmac,
            admission_condition=application.admission_condition,
            rank=application.rank,
            competitive_score=application.competitive_score,
            enrollment_priority=application.enrollment_priority,
            consent=application.consent,
            application_status=application.application_status,
            bvi=bool(application.raw_payload.get("bvi", False)),
            advantages=application.raw_payload.get("is_have_advantages"),
            seat_count=seat_count,
            data_complete=coverage.complete,
            global_event_summary=GlobalEventSummary({}),
            local_target_signals=LocalTargetSignals(),
            retention_calibration=calibration,
            candidate_cohorts=cohorts,
            cross_group_excluded_ahead=cross_group_excluded,
        )
        # Retain the current heuristic beside the new model for later calibration review.
        deterministic_output = AdmissionProbabilityEngine().calculate(value)
        await persist_forecast(
            uow,
            tracked_user_id=target.tracked_user_id,
            user_target_id=target.id,
            value=value,
            output=deterministic_output,
        )
        output = ProbabilisticAdmissionEngine().calculate(value)
        _, was_created = await persist_forecast(
            uow,
            tracked_user_id=target.tracked_user_id,
            user_target_id=target.id,
            value=value,
            output=output,
        )
        created += was_created
    return ForecastRecomputeOutcome(created=created, skipped=skipped)


@dataclass(frozen=True)
class UniversityCoverage:
    complete: bool
    group_count: int
    current_snapshot_count: int
    snapshots_by_group: dict[UUID, ListSnapshot]


async def _university_coverage(
    uow: UnitOfWork, group: CompetitionGroup, snapshot: ListSnapshot
) -> UniversityCoverage:
    groups = list(
        (
            await uow.session.scalars(
                select(CompetitionGroup).where(
                    CompetitionGroup.university_id == group.university_id,
                    CompetitionGroup.campaign_year == group.campaign_year,
                    CompetitionGroup.identity_namespace == group.identity_namespace,
                )
            )
        ).all()
    )
    batch = snapshot.raw_payload.get("ingestion_batch")
    if not isinstance(batch, dict) or not isinstance(batch.get("id"), str):
        return UniversityCoverage(False, len(groups), 0, {})
    batch_id = batch["id"]
    expected_group_count = batch.get("expected_group_count")
    if not isinstance(expected_group_count, int) or expected_group_count != len(groups):
        return UniversityCoverage(False, len(groups), 0, {})
    snapshots = list(
        (
            await uow.session.scalars(
                select(ListSnapshot).where(
                    ListSnapshot.campaign_year == snapshot.campaign_year,
                    ListSnapshot.status == SnapshotStatus.VALID,
                    ListSnapshot.competition_group_id.in_([item.id for item in groups]),
                )
            )
        ).all()
    )
    snapshots_by_group = {
        item.competition_group_id: item
        for item in snapshots
        if _batch_id(item) == batch_id
    }
    return UniversityCoverage(
        complete=bool(groups) and len(snapshots_by_group) == len(groups),
        group_count=len(groups),
        current_snapshot_count=len(snapshots_by_group),
        snapshots_by_group=snapshots_by_group,
    )


async def _history_to_snapshot(uow: UnitOfWork, snapshot: ListSnapshot) -> list[ListSnapshot]:
    snapshots = list(
        (
            await uow.session.scalars(
                select(ListSnapshot)
                .where(
                    ListSnapshot.competition_group_id == snapshot.competition_group_id,
                    ListSnapshot.status == SnapshotStatus.VALID,
                )
                .order_by(ListSnapshot.fetched_at, ListSnapshot.id)
            )
        ).all()
    )
    index = next(index for index, item in enumerate(snapshots) if item.id == snapshot.id)
    return snapshots[: index + 1]


async def _applications_for_snapshots(
    uow: UnitOfWork, snapshot_ids: list[UUID]
) -> dict[UUID, list[Application]]:
    grouped: dict[UUID, list[Application]] = {snapshot_id: [] for snapshot_id in snapshot_ids}
    rows = await uow.session.scalars(
        select(Application).where(Application.snapshot_id.in_(snapshot_ids))
    )
    for application in rows:
        grouped[application.snapshot_id].append(application)
    return grouped


def _calibrations(
    history: list[ListSnapshot], applications: dict[UUID, list[Application]]
) -> dict[str, RetentionCalibration]:
    observations: Counter[str] = Counter()
    retained: Counter[str] = Counter()
    for previous, current in zip(history, history[1:], strict=True):
        previous_by_condition = _uids_by_condition(applications[previous.id])
        current_by_condition = _uids_by_condition(applications[current.id])
        for condition, previous_uids in previous_by_condition.items():
            observations[condition] += len(previous_uids)
            retained[condition] += len(previous_uids & current_by_condition.get(condition, set()))
    return {
        condition: RetentionCalibration(
            retained=retained[condition],
            observations=count,
            snapshot_count=len(history),
        )
        for condition, count in observations.items()
    }


def _uids_by_condition(applications: list[Application]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for application in applications:
        result.setdefault(application.admission_condition, set()).add(
            application.applicant_uid_hmac
        )
    return result


def _target_application(applications: list[Application], target: UserTarget) -> Application | None:
    candidates = [
        application
        for application in applications
        if application.applicant_uid_hmac == target.applicant_uid_hmac
        and application.identity_namespace == target.identity_namespace
    ]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda application: (
            application.admission_condition != "general_competition",
            application.rank,
        ),
    )


def _seat_count(snapshot: ListSnapshot, condition: str) -> int | None:
    seat_counts = snapshot.raw_payload.get("seat_counts")
    if not isinstance(seat_counts, dict):
        return None
    value = seat_counts.get(condition)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        return None
    return value


def _batch_id(snapshot: ListSnapshot) -> str | None:
    batch = snapshot.raw_payload.get("ingestion_batch")
    return batch.get("id") if isinstance(batch, dict) and isinstance(batch.get("id"), str) else None


def _applications_by_uid(
    application_groups: Iterable[list[Application]],
) -> dict[str, list[Application]]:
    result: dict[str, list[Application]] = {}
    for applications in application_groups:
        for application in applications:
            result.setdefault(application.applicant_uid_hmac, []).append(application)
    return result


def _candidate_cohorts(
    applications: list[Application],
    target: Application,
    applications_by_uid: dict[str, list[Application]],
) -> tuple[tuple[CandidateCohort, ...], int]:
    counts: Counter[float] = Counter()
    cross_group_excluded = 0
    for application in applications:
        if (
            application.admission_condition == target.admission_condition
            and application.rank < target.rank
        ):
            if _has_higher_priority_application(
                application, applications_by_uid[application.applicant_uid_hmac]
            ):
                cross_group_excluded += 1
                continue
            counts[_stay_adjustment(application)] += 1
    return (
        tuple(
            CandidateCohort(count=count, stay_adjustment=adjustment)
            for adjustment, count in sorted(counts.items())
        ),
        cross_group_excluded,
    )


def _has_higher_priority_application(
    application: Application, alternatives: list[Application]
) -> bool:
    for alternative in alternatives:
        if alternative.competition_group_id == application.competition_group_id:
            continue
        if (
            alternative.consent is True
            and alternative.raw_payload.get("main_top_priority") is True
            and alternative.raw_payload.get("highest_passageway_priority") is True
        ):
            return True
    return False


def _stay_adjustment(application: Application) -> float:
    adjustment = 0.0
    if application.consent is True:
        adjustment += 0.12
    elif application.consent is False:
        adjustment -= 0.18
    if application.enrollment_priority == 1:
        adjustment += 0.04
    elif application.enrollment_priority is not None and application.enrollment_priority > 3:
        adjustment -= 0.02
    return adjustment
