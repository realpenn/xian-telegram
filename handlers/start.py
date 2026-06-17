"""/start —— 注册 + 测灵根。"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from handlers.common import guard_private_callback, guard_private_message, main_menu, show
from services import character

router = Router()

MENU_TEXT = "🏯 主菜单\n道友请择一处前往，或发送 /me 查看道行。"


@router.message(Command("start"))
async def cmd_start(message: Message):
    if await guard_private_message(message):
        return
    uid = message.from_user.id
    username = message.from_user.username or message.from_user.full_name
    if await character.exists(uid):
        await character.touch_user(uid, username)
        await message.answer("道友已在途中。发送 /me 查看道行，或点下方按钮。",
                             reply_markup=main_menu())
        return
    char = await character.create(uid, username)
    text = (
        "🌅 一道流光没入识海，道友自此踏上仙途！\n\n"
        "—— 测灵根 ——\n"
        f"你天生【{char.spirit_root}】，根骨 {char.root_bone}。\n"
        "初入【炼气期·一层】，得灵石 100、新手木剑一柄、战技「快剑斩」。\n\n"
        "发送 /help 查看修行法门，或点下方按钮起步。"
    )
    await message.answer(text, reply_markup=main_menu())


@router.callback_query(F.data == "nav:menu")
async def cb_menu(callback: CallbackQuery):
    if await guard_private_callback(callback):
        return
    await show(callback, MENU_TEXT, main_menu())
    await callback.answer()
