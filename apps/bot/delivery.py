import asyncio
from datetime import UTC, datetime

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.bot.keyboards import notification_keyboard
from packages.notifications.service import text
from packages.persistence.uow import UnitOfWork

POLL_INTERVAL_SECONDS = 5
MAX_ATTEMPTS = 3


async def deliver_pending_notifications(
    bot: Bot, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    while True:
        await _deliver_once(bot, session_factory)
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


async def _deliver_once(bot: Bot, session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with UnitOfWork(session_factory) as uow:
        for notification in await uow.notifications.list_deliverable(
            limit=50, max_attempts=MAX_ATTEMPTS
        ):
            if notification.user_target_id is None:
                await uow.notifications.mark_skipped(notification, "target_deleted")
                continue
            user = await uow.users.get(notification.tracked_user_id)
            if user is None:
                await uow.notifications.mark_skipped(notification, "user_deleted")
                continue
            content = notification.payload
            try:
                await bot.send_message(
                    user.telegram_user_id,
                    text(
                        low=float(content["probability_low"]),
                        high=float(content["probability_high"]),
                        confidence=str(content["confidence"]),
                        reason=str(content["reason"]),
                    ),
                    reply_markup=notification_keyboard(str(notification.user_target_id)),
                )
            except Exception:
                await uow.notifications.mark_failed(notification, "telegram_delivery_failed")
            else:
                await uow.notifications.mark_sent(notification, datetime.now(UTC))
