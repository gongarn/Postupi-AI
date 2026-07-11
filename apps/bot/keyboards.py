from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


class BotCallback(CallbackData, prefix="postupi"):
    action: str
    token: str | None = None


def start_keyboard() -> InlineKeyboardMarkup:
    callback = BotCallback(action="tracks").pack()
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Мои направления", callback_data=callback)]
        ]
    )


def tracks_keyboard(target_ids: list[str]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"Направление {index}",
                callback_data=BotCallback(action="target", token=target_id).pack(),
            )
        ]
        for index, target_id in enumerate(target_ids, start=1)
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data=BotCallback(action="tracks").pack())]
        ]
    )
