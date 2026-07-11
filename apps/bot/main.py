import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.bot.handlers.system import router
from packages.common.config import get_settings

session_factory: async_sessionmaker[AsyncSession] | None = None


async def main() -> None:
    global session_factory
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("POSTUPI_TELEGRAM_BOT_TOKEN is required for the bot")
    bot = Bot(
        token=settings.telegram_bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    engine = create_async_engine(str(settings.database_url), pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    try:
        await dispatcher.start_polling(bot)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
