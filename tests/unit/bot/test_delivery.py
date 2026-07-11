import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from apps.bot.delivery import _deliver_once


class Notifications:
    def __init__(self, notification: object) -> None:
        self.notification = notification
        self.state = ""

    async def list_deliverable(self, **_: object) -> list[object]:
        return [self.notification]

    async def mark_sent(self, _: object, __: object) -> None:
        self.state = "sent"

    async def mark_failed(self, _: object, __: object) -> None:
        self.state = "failed"

    async def mark_skipped(self, _: object, __: object) -> None:
        self.state = "skipped"


class UserRepository:
    async def get(self, _: object) -> object:
        return SimpleNamespace(telegram_user_id=1)


class UnitOfWorkStub:
    def __init__(self, notification: object) -> None:
        self.notifications = Notifications(notification)
        self.users = UserRepository()

    async def __aenter__(self) -> "UnitOfWorkStub":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None


def test_delivery_marks_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    notification = SimpleNamespace(
        tracked_user_id=uuid4(),
        user_target_id=uuid4(),
        payload={
            "probability_low": 0.2,
            "probability_high": 0.4,
            "confidence": "medium",
            "reason": "material_forecast",
        },
    )
    uow = UnitOfWorkStub(notification)

    class Bot:
        async def send_message(self, *_: object, **__: object) -> None:
            return None

    monkeypatch.setattr("apps.bot.delivery.UnitOfWork", lambda _: uow)
    asyncio.run(_deliver_once(Bot(), object()))
    assert uow.notifications.state == "sent"
