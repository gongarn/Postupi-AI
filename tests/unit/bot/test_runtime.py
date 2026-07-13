from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.bot import runtime
from apps.bot.handlers.system import _session_factory


def test_handlers_use_shared_bot_runtime_session_factory() -> None:
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker()
    runtime.session_factory = factory
    try:
        assert _session_factory() is factory
    finally:
        runtime.session_factory = None
