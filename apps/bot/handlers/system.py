from uuid import UUID

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.bot.keyboards import BotCallback, back_keyboard, start_keyboard, tracks_keyboard
from apps.bot.presenters import (
    empty_tracks_text,
    help_text,
    start_text,
    track_detail_text,
    tracks_text,
)
from apps.bot.service import get_track_view, list_track_views

router = Router(name="system")


def _session_factory() -> async_sessionmaker[AsyncSession]:
    from apps.bot.main import session_factory

    if session_factory is None:
        raise RuntimeError("bot database is not initialized")
    return session_factory


@router.message(Command("start"))
async def start(message: Message) -> None:
    await message.answer(start_text(), reply_markup=start_keyboard())


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(help_text())


@router.message(Command("tracks"))
async def tracks(message: Message) -> None:
    async with _session_factory()() as session:
        views = await list_track_views(session, message.from_user.id if message.from_user else 0)
    if not views:
        await message.answer(empty_tracks_text())
        return
    await message.answer(
        tracks_text(views),
        reply_markup=tracks_keyboard([view.target_id for view in views]),
    )


@router.callback_query(BotCallback.filter())
async def callback_navigation(query: CallbackQuery, callback_data: BotCallback) -> None:
    if query.message is None or query.from_user is None:
        return
    async with _session_factory()() as session:
        if callback_data.action == "tracks":
            views = await list_track_views(session, query.from_user.id)
            text = empty_tracks_text() if not views else tracks_text(views)
            markup = None if not views else tracks_keyboard([view.target_id for view in views])
        elif callback_data.action == "target" and callback_data.token:
            try:
                target_id = UUID(callback_data.token)
            except ValueError:
                await query.answer("Недоступно", show_alert=True)
                return
            view = await get_track_view(session, query.from_user.id, target_id)
            if view is None:
                await query.answer("Направление не найдено", show_alert=True)
                return
            text, markup = track_detail_text(view), back_keyboard()
        else:
            await query.answer("Недоступно", show_alert=True)
            return
    if isinstance(query.message, Message):
        await query.message.edit_text(text, reply_markup=markup)
    await query.answer()
