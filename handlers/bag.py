"""/bag —— 最简储物袋。"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from config.items import item_name
from handlers.common import NEED_START, main_menu, show
from services import character

router = Router()


async def render_bag(user_id: int):
    char = await character.get(user_id)
    if not char:
        return NEED_START, None
    inv = await character.inventory(user_id)
    lines = ["🎒 储物袋", f"🪙 灵石 {char.spirit_stone}"]
    if inv:
        lines.append("—— 物品 ——")
        lines += [f"{item_name(k)} ×{q}" for k, q in inv]
    else:
        lines.append("（空空如也，去历练寻些机缘吧）")
    return "\n".join(lines), main_menu()


@router.message(Command("bag"))
async def cmd_bag(message: Message):
    text, markup = await render_bag(message.from_user.id)
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "nav:bag")
async def cb_bag(callback: CallbackQuery):
    text, markup = await render_bag(callback.from_user.id)
    await show(callback, text, markup)
    await callback.answer()
