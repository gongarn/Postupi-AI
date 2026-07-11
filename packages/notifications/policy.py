import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class NotificationDecision:
    meaningful: bool
    reason: str
    delivery_key: str

def decide(
    *,
    target_id: str,
    snapshot_id: str,
    engine_version: str,
    previous: tuple[float, float, str] | None,
    current: tuple[float, float, str],
    local_events: dict[str, int],
) -> NotificationDecision:
    shifted = previous is not None and max(
        abs(previous[0] - current[0]), abs(previous[1] - current[1])
    ) >= 0.10
    confidence_changed = previous is not None and previous[2] != current[2]
    important = sum(
        local_events.get(key, 0) for key in ("appeared", "disappeared", "rank_changed")
    ) > 0
    reason = (
        "material_forecast"
        if shifted or confidence_changed
        else "near_threshold_event"
        if important
        else "noise"
    )
    key_material = f"{target_id}:{snapshot_id}:{engine_version}:{reason}"
    key = hashlib.sha256(key_material.encode()).hexdigest()
    return NotificationDecision(reason != "noise", reason, key)
