from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from packages.notifications.policy import NotificationDecision
from packages.persistence.models import Notification
from packages.persistence.uow import UnitOfWork


def text(*, low: float, high: float, confidence: str, reason: str) -> str:
    return (
        f"Обновление по направлению: вероятность {low:.0%}–{high:.0%}, "
        f"уверенность: {confidence}. Причина: {reason}."
    )

async def deliver(send: Callable[[str], Awaitable[None]], message: str) -> str:
    try:
        await send(message)
        return "sent"
    except Exception:
        return "retry"


def payload(*, low: float, high: float, confidence: str, reason: str) -> dict[str, Any]:
    return {
        "probability_low": low,
        "probability_high": high,
        "confidence": confidence,
        "reason": reason,
    }


async def queue(
    uow: UnitOfWork,
    *,
    tracked_user_id: UUID,
    user_target_id: UUID,
    snapshot_id: UUID,
    engine_version: str,
    decision: NotificationDecision,
    content: dict[str, Any],
) -> Notification | None:
    if not decision.meaningful:
        return None
    existing = await uow.notifications.get_by_delivery_key(
        tracked_user_id=tracked_user_id,
        user_target_id=user_target_id,
        delivery_key=decision.delivery_key,
    )
    if existing is not None:
        return existing
    return await uow.notifications.add(
        tracked_user_id=tracked_user_id,
        user_target_id=user_target_id,
        current_snapshot_id=snapshot_id,
        engine_version=engine_version,
        delivery_key=decision.delivery_key,
        kind=decision.reason,
        payload=content,
    )
