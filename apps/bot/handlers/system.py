from uuid import UUID

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.bot.keyboards import (
    BotCallback,
    back_keyboard,
    competition_groups_keyboard,
    start_keyboard,
    tracks_keyboard,
    universities_keyboard,
)
from apps.bot.presenters import (
    empty_tracks_text,
    help_text,
    start_text,
    track_detail_text,
    tracks_text,
)
from apps.bot.service import get_track_view, list_track_views
from apps.bot.target_api import (
    TargetAlreadyExistsError,
    TargetAPIError,
    create_target,
    list_competition_groups,
)
from packages.common.config import get_settings

router = Router(name="system")
GROUPS_PER_PAGE = 8


class AddTarget(StatesGroup):
    awaiting_uid = State()


def _session_factory() -> async_sessionmaker[AsyncSession]:
    from apps.bot.runtime import session_factory

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


@router.callback_query(BotCallback.filter(F.action == "add"))
async def add_target(query: CallbackQuery, callback_data: BotCallback) -> None:
    try:
        page = int(callback_data.token) if callback_data.token else 0
    except ValueError:
        page = 0
    if page < 0:
        page = 0
    settings = get_settings()
    if settings.internal_api_token is None:
        await query.answer("Сервис временно недоступен", show_alert=True)
        return
    try:
        groups = await list_competition_groups(
            base_url=settings.internal_api_base_url,
            token=settings.internal_api_token.get_secret_value(),
        )
    except TargetAPIError:
        await query.answer("Сервис временно недоступен", show_alert=True)
        return
    if not groups:
        await query.answer("Нет доступных направлений", show_alert=True)
        return
    universities = {str(group.university_id): group.university_name for group in groups}
    university_options = sorted(universities.items(), key=lambda item: item[1])
    if query.message is not None:
        await query.message.answer(
            "Выберите вуз:",
            reply_markup=universities_keyboard(university_options),
        )
    await query.answer()


@router.callback_query(BotCallback.filter(F.action == "university"))
async def choose_university(query: CallbackQuery, callback_data: BotCallback) -> None:
    if callback_data.token is None:
        await query.answer("Недоступно", show_alert=True)
        return
    settings = get_settings()
    if settings.internal_api_token is None:
        await query.answer("Сервис временно недоступен", show_alert=True)
        return
    try:
        university_id = UUID(callback_data.token)
        groups = await list_competition_groups(
            base_url=settings.internal_api_base_url,
            token=settings.internal_api_token.get_secret_value(),
        )
    except (TargetAPIError, ValueError):
        await query.answer("Сервис временно недоступен", show_alert=True)
        return
    page_groups = [group for group in groups if group.university_id == university_id]
    if not page_groups:
        await query.answer("Недоступно", show_alert=True)
        return
    if query.message is not None:
        await query.message.answer(
            "Выберите направление:",
            reply_markup=competition_groups_keyboard(
                [
                    (str(group.id), f"{group.university_name}: {group.title}")
                    for group in page_groups
                ],
            ),
        )
    await query.answer()


@router.callback_query(BotCallback.filter(F.action == "group"))
async def choose_competition_group(
    query: CallbackQuery, callback_data: BotCallback, state: FSMContext
) -> None:
    if callback_data.token is None:
        await query.answer("Недоступно", show_alert=True)
        return
    try:
        group_id = UUID(callback_data.token)
    except ValueError:
        await query.answer("Недоступно", show_alert=True)
        return
    await state.set_state(AddTarget.awaiting_uid)
    await state.update_data(competition_group_id=str(group_id))
    if query.message is not None:
        await query.message.answer("Отправьте ваш код абитуриента из конкурсного списка.")
    await query.answer()


@router.message(AddTarget.awaiting_uid)
async def save_target(message: Message, state: FSMContext) -> None:
    if message.from_user is None or not message.text:
        await message.answer("Отправьте код абитуриента текстом.")
        return
    data = await state.get_data()
    group_id = data.get("competition_group_id")
    if not isinstance(group_id, str):
        await state.clear()
        await message.answer("Выберите направление заново.", reply_markup=start_keyboard())
        return
    settings = get_settings()
    if settings.internal_api_token is None:
        await message.answer("Сервис временно недоступен.")
        return
    try:
        await create_target(
            base_url=settings.internal_api_base_url,
            token=settings.internal_api_token.get_secret_value(),
            telegram_user_id=message.from_user.id,
            competition_group_id=UUID(group_id),
            applicant_uid=message.text,
        )
    except TargetAlreadyExistsError:
        await state.clear()
        await message.answer("Это направление уже отслеживается.", reply_markup=start_keyboard())
        return
    except (TargetAPIError, ValueError):
        await message.answer("Не удалось добавить направление. Попробуйте ещё раз.")
        return
    await state.clear()
    await message.answer("Направление добавлено.", reply_markup=start_keyboard())


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
