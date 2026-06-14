"""/dungeon —— 秘境副本。"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config.dungeons import DUNGEONS
from config.items import item_name
from handlers.common import (NEED_START, action_callback_data, consume_action_callback,
                             guard_private_callback, guard_private_message, main_menu, show)
from services import character, dungeon

router = Router()


async def render_dungeon(user_id: int):
    char = await character.get(user_id)
    if not char:
        return NEED_START, None
    rows = []
    lines = ["🏯 秘境", "每日每处秘境可入 1 次。"]
    for key, d in DUNGEONS.items():
        state = "可入" if char.realm >= d["realm"] else "未解锁"
        lines.append(f"{d['name']}：{d['layers']} 层，每层精力 {d['stamina']}（{state}）")
        if char.realm >= d["realm"]:
            rows.append([InlineKeyboardButton(
                text=f"进入 {d['name']}",
                callback_data=await action_callback_data(user_id, f"dg:{key}"))])
    rows += main_menu().inline_keyboard
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


def _result_text(res: dict) -> str:
    s = res["status"]
    if s == "locked":
        return f"秘境云封雾锁，需至 {res['need']} 方可入内。"
    if s == "daily_done":
        return "今日已探过此秘境，且待明日。"
    if s == "in_seclusion":
        return "道友仍在闭关，不可入秘境。"
    if s == "no_stamina":
        return f"精力不济（需 {res['need']}，余 {res['have']}）。"
    if s == "missing":
        return NEED_START
    if s == "bad_dungeon":
        return "查无此秘境。"
    rw = res["reward"]
    parts = [f"🪙{rw['stone']}", f"修为+{rw['cult']}"]
    if rw["drops"]:
        parts.append("、".join(f"{item_name(k)}×{v}" for k, v in rw["drops"].items()))
    if rw["equipment"]:
        parts.append("法宝：" + "、".join(rw["equipment"]))
    return "\n".join([
        f"🏯 {res['dungeon']}：深入 {res['cleared']}/{res['layers']} 层。",
        *res["log"],
        "🎁 收获：" + "，".join(parts),
        f"⚡ 精力余 {res['stamina_left']}",
    ])


@router.message(Command("dungeon"))
async def cmd_dungeon(message: Message):
    if await guard_private_message(message):
        return
    text, markup = await render_dungeon(message.from_user.id)
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "nav:dungeon")
async def cb_dungeon(callback: CallbackQuery):
    if await guard_private_callback(callback):
        return
    text, markup = await render_dungeon(callback.from_user.id)
    await show(callback, text, markup)
    await callback.answer()


@router.callback_query(F.data.startswith("dg:"))
async def cb_dungeon_run(callback: CallbackQuery):
    if await guard_private_callback(callback):
        return
    action = await consume_action_callback(callback)
    if not action or not action.startswith("dg:"):
        return
    res = await dungeon.run(callback.from_user.id, action[3:])
    await show(callback, _result_text(res), main_menu())
    await callback.answer()
