from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


class BotCallback(CallbackData, prefix="postupi"):
    action: str
    token: str | None = None


def start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Мои направления", callback_data=BotCallback(action="tracks").pack()
                )
            ],
            [
                InlineKeyboardButton(
                    text="Добавить направление", callback_data=BotCallback(action="add").pack()
                )
            ],
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
    rows.append(
        [
            InlineKeyboardButton(
                text="Добавить направление", callback_data=BotCallback(action="add").pack()
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def competition_groups_keyboard(groups: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=label[:64],
                    callback_data=BotCallback(action="group", token=group_id).pack(),
                )
            ]
            for group_id, label in groups
        ]
    )


def universities_keyboard(universities: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=name[:64],
                    callback_data=BotCallback(action="university", token=university_id).pack(),
                )
            ]
            for university_id, name in universities
        ]
    )


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data=BotCallback(action="tracks").pack())]
        ]
    )


def notification_keyboard(target_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Открыть направление",
                    callback_data=BotCallback(action="target", token=target_id).pack(),
                )
            ]
        ]
    )
