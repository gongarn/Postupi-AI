from apps.bot.handlers.system import router


def test_system_router_is_configured() -> None:
    assert router.name == "system"
