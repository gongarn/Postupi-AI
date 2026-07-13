import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.bot import runtime
from apps.bot.delivery import deliver_pending_notifications
from apps.bot.handlers.system import router
from packages.common.config import get_settings


async def main() -> None:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("POSTUPI_TELEGRAM_BOT_TOKEN is required for the bot")
    bot = Bot(
        token=settings.telegram_bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    engine = create_async_engine(str(settings.database_url), pool_pre_ping=True)
    runtime.session_factory = async_sessionmaker(engine, expire_on_commit=False)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    delivery_task = asyncio.create_task(deliver_pending_notifications(bot, runtime.session_factory))
    try:
        await dispatcher.start_polling(bot)
    finally:
        delivery_task.cancel()
        await asyncio.gather(delivery_task, return_exceptions=True)
        runtime.session_factory = None
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
