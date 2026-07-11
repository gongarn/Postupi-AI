import asyncio

from apps.worker.jobs import system_ping


def test_system_ping_returns_serializable_result() -> None:
    result = asyncio.run(system_ping(None))
    assert result["status"] == "ok"
    assert "timestamp" in result
