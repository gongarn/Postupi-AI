import asyncio

from packages.notifications.service import deliver, payload, text


def test_notification_text_and_payload_are_private() -> None:
    value = text(low=.2, high=.4, confidence="medium", reason="material_forecast")
    content = payload(low=.2, high=.4, confidence="medium", reason="material_forecast")
    assert "20%" in value
    assert "raw_payload" not in value
    assert "hmac" not in value.lower()
    assert set(content) == {"probability_low", "probability_high", "confidence", "reason"}


def test_delivery_returns_retry_without_provider_error() -> None:
    async def fail(_: str) -> None:
        raise RuntimeError("provider body must not escape")

    assert asyncio.run(deliver(fail, "synthetic")) == "retry"
