from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select

from packages.persistence.event_repository import EventRepository
from packages.persistence.models import Application, ListSnapshot, SnapshotStatus
from packages.persistence.uow import UnitOfWork

DIFF_VERSION = "snapshot-diff-1"
EVENT_TYPES = {
    "appeared", "disappeared", "rank_changed", "score_changed", "priority_changed",
    "consent_changed", "status_changed", "bvi_changed", "advantages_changed", "condition_changed",
}
_STATE_FIELDS = {
    "rank", "competitive_score", "enrollment_priority", "consent", "application_status",
    "bvi", "advantages", "main_top_priority", "highest_passageway_priority",
}


@dataclass(frozen=True)
class DiffOutcome:
    event_counts: dict[str, int]
    skipped: bool = False


async def diff_snapshots(
    uow: UnitOfWork, *, previous_snapshot_id: UUID, current_snapshot_id: UUID
) -> DiffOutcome:
    previous = await uow.session.get(ListSnapshot, previous_snapshot_id)
    current = await uow.session.get(ListSnapshot, current_snapshot_id)
    _validate_snapshots(previous, current)
    assert previous is not None
    assert current is not None
    if previous.content_hash == current.content_hash:
        return DiffOutcome({}, skipped=True)

    previous_apps = await _applications(uow, previous.id)
    current_apps = await _applications(uow, current.id)
    previous_by_key = {
        (item.applicant_uid_hmac, item.admission_condition): item
        for item in previous_apps
    }
    current_by_key = {
        (item.applicant_uid_hmac, item.admission_condition): item
        for item in current_apps
    }
    previous_by_uid = _by_uid(previous_apps)
    current_by_uid = _by_uid(current_apps)
    changed_keys: set[tuple[str, str]] = set()
    counts: Counter[str] = Counter()
    repository = EventRepository(uow.session)

    for uid in sorted(set(previous_by_uid) | set(current_by_uid)):
        old_conditions = set(previous_by_uid.get(uid, {}))
        new_conditions = set(current_by_uid.get(uid, {}))
        for old_condition, new_condition in _condition_changes(old_conditions, new_conditions):
            changed_keys.update({(uid, old_condition), (uid, new_condition)})
            old_app = previous_by_uid[uid][old_condition]
            new_app = current_by_uid[uid][new_condition]
            if await _save(
                repository,
                previous,
                current,
                old_app,
                new_app,
                "condition_changed",
                old_condition,
                new_condition,
            ):
                counts["condition_changed"] += 1

    for key in sorted(set(previous_by_key) | set(current_by_key)):
        if key in changed_keys:
            continue
        old = previous_by_key.get(key)
        new = current_by_key.get(key)
        if old is None:
            event_type = "appeared"
        elif new is None:
            event_type = "disappeared"
        else:
            for event_type, field in (
                ("rank_changed", "rank"), ("score_changed", "competitive_score"),
                ("priority_changed", "enrollment_priority"), ("consent_changed", "consent"),
                ("status_changed", "application_status"), ("bvi_changed", "bvi"),
                ("advantages_changed", "advantages"),
            ):
                if _state(old)[field] != _state(new)[field]:
                    if await _save(
                        repository,
                        previous,
                        current,
                        old,
                        new,
                        event_type,
                        old.admission_condition,
                        new.admission_condition,
                    ):
                        counts[event_type] += 1
            continue
        if await _save(
            repository,
            previous,
            current,
            old,
            new,
            event_type,
            old.admission_condition if old is not None else None,
            new.admission_condition if new is not None else None,
        ):
            counts[event_type] += 1
    await uow.session.flush()
    return DiffOutcome(dict(counts))


async def _applications(uow: UnitOfWork, snapshot_id: UUID) -> list[Application]:
    result = await uow.session.scalars(
        select(Application).where(Application.snapshot_id == snapshot_id)
    )
    return list(result)


def _by_uid(applications: list[Application]) -> dict[str, dict[str, Application]]:
    result: dict[str, dict[str, Application]] = {}
    for application in applications:
        result.setdefault(application.applicant_uid_hmac, {})[
            application.admission_condition
        ] = application
    return result


def _condition_changes(old: set[str], new: set[str]) -> list[tuple[str, str]]:
    return [
        (old_condition, new_condition)
        for old_condition in sorted(old - new)
        for new_condition in sorted(new - old)
    ]


def _state(application: Application) -> dict[str, Any]:
    payload = application.raw_payload
    state = {
        "rank": application.rank,
        "competitive_score": application.competitive_score,
        "enrollment_priority": application.enrollment_priority,
        "consent": application.consent,
        "application_status": application.application_status,
        "bvi": payload.get("bvi", application.admission_condition == "without_entry_tests"),
        "advantages": payload.get("is_have_advantages"),
        "main_top_priority": payload.get("main_top_priority"),
        "highest_passageway_priority": payload.get("highest_passageway_priority"),
    }
    return {key: state[key] for key in _STATE_FIELDS}


async def _save(
    repository: EventRepository,
    previous: ListSnapshot,
    current: ListSnapshot,
    old: Application | None,
    new: Application | None,
    event_type: str,
    previous_condition: str | None,
    current_condition: str | None,
) -> bool:
    item = old or new
    assert item is not None
    before = _state(old) if old else {}
    after = _state(new) if new else {}
    _validate_payload(before, after, item.applicant_uid_hmac)
    return await repository.add_ignore_duplicate(
        competition_group_id=current.competition_group_id,
        applicant_uid_hmac=item.applicant_uid_hmac,
        identity_namespace=item.identity_namespace,
        previous_snapshot_id=previous.id,
        current_snapshot_id=current.id,
        previous_admission_condition=previous_condition,
        current_admission_condition=current_condition,
        event_type=event_type,
        before_json=before,
        after_json=after,
        diff_version=DIFF_VERSION,
    )


def _validate_snapshots(previous: ListSnapshot | None, current: ListSnapshot | None) -> None:
    if previous is None or current is None:
        raise ValueError("snapshot pair not found")
    if previous.id == current.id:
        raise ValueError("snapshot pair must be distinct")
    if previous.competition_group_id != current.competition_group_id:
        raise ValueError("snapshot groups differ")
    if previous.campaign_year != current.campaign_year:
        raise ValueError("snapshot campaigns differ")
    if previous.status != SnapshotStatus.VALID or current.status != SnapshotStatus.VALID:
        raise ValueError("only valid snapshots can be compared")


def _validate_payload(before: dict[str, Any], after: dict[str, Any], raw_uid: str) -> None:
    for payload in (before, after):
        if set(payload) - _STATE_FIELDS:
            raise ValueError("event payload contains unknown fields")
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        if (
            raw_uid in serialized
            or "sspvo_id" in serialized
            or "link" in serialized
            or "raw_payload" in serialized
        ):
            raise ValueError("raw identity data in event payload")
