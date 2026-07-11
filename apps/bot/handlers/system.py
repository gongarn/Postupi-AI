from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router(name="system")


@router.message(Command("start"))
async def start(message: Message) -> None:
    await message.answer(
        "Postupi AI пока находится в техническом пилоте. Используйте /help, "
        "чтобы увидеть доступные команды."
    )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer("Доступно: /start и /help.")
