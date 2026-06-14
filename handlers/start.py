"""/start —— 注册 + 测灵根。"""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from handlers.common import guard_private_message, main_menu
from services import character

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    if await guard_private_message(message):
        return
    uid = message.from_user.id
    if await character.exists(uid):
        await message.answer("道友已在途中。发送 /me 查看道行，或点下方按钮。",
                             reply_markup=main_menu())
        return
    char = await character.create(uid, message.from_user.username or message.from_user.full_name)
    text = (
        "🌅 一道流光没入识海，道友自此踏上仙途！\n\n"
        "—— 测灵根 ——\n"
        f"你天生【{char.spirit_root}】，根骨 {char.root_bone}。\n"
        "初入【炼气期·一层】，得灵石 100、新手木剑一柄、战技「快剑斩」。\n\n"
        "发送 /help 查看修行法门，或点下方按钮起步。"
    )
    await message.answer(text, reply_markup=main_menu())
