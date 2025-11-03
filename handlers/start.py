from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from templates.messages import START_TEXT, HELP_TEXT, ABOUT_TEXT, SETTINGS_TEXT
from templates.buttons import main_menu_kb, settings_kb

router = Router(name=__name__)

@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(START_TEXT, reply_markup=main_menu_kb())

@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(HELP_TEXT, reply_markup=main_menu_kb())

@router.message(Command("about"))
async def cmd_about(message: Message):
    await message.answer(ABOUT_TEXT, reply_markup=main_menu_kb())

@router.message(Command("settings"))
async def cmd_settings(message: Message):
    await message.answer(SETTINGS_TEXT, reply_markup=settings_kb())
