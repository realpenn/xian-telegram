"""/help —— 指南。"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from config.copy import HELP
from handlers.common import main_menu, show

router = Router()


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(HELP, reply_markup=main_menu())


@router.callback_query(F.data == "nav:help")
async def cb_help(callback: CallbackQuery):
    await show(callback, HELP, main_menu())
    await callback.answer()
