"""/explore —— 选图历练 + 战斗结算。"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, Message)

from config import realms as R
from config.items import item_name
from config.maps import maps_for_realm
from handlers.common import (NEED_START, guard_private_callback, guard_private_message,
                             action_callback_data, consume_action_callback, main_menu, show)
from services import character
from services import explore as explore_service

router = Router()


async def render_menu(user_id: int):
    char = await character.get(user_id)
    if not char:
        return NEED_START, None
    welfare = await character.sect_welfare(user_id)
    cap = R.STAMINA_CAP[char.realm] + welfare["stamina_bonus"]
    rows = []
    for key, m in maps_for_realm(char.realm):
        rows.append([InlineKeyboardButton(
            text=f"{m['name']}（精力{m['stamina']}）",
            callback_data=await action_callback_data(user_id, f"ex:{key}"))])
    rows += main_menu().inline_keyboard
    text = f"⚔️ 历练\n⚡ 精力 {char.stamina}/{cap}\n择一处历练之地，斩妖夺宝："
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


async def _after_markup(user_id: int, map_key: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(
        text="🔁 再历练一次",
        callback_data=await action_callback_data(user_id, f"ex:{map_key}")),
        InlineKeyboardButton(text="⚔️ 换地图", callback_data="nav:explore")]]
    rows += main_menu().inline_keyboard
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _result_text(res: dict) -> str:
    s = res["status"]
    if s == "locked":
        return f"此地凶险，需修为至 {res['need']} 方可踏足。"
    if s == "in_seclusion":
        return "道友尚在闭关，神游太虚，不可同时外出历练。"
    if s == "no_stamina":
        return f"精力不济（需 {res['need']}，余 {res['have']}），且去闭关歇息。"
    if s == "missing":
        return NEED_START
    if s == "bad_map":
        return "查无此地。"
    log = res["log"]
    shown = log if len(log) <= 11 else (log[:10] + ["……", log[-1]])
    lines = []
    if res["is_boss"]:
        lines.append("🐲 妖王现身！")
    lines += shown
    if res["win"]:
        rw = res["reward"]
        parts = [f"🪙{rw['stone']}", f"修为+{rw['cult']}"]
        if rw["drops"]:
            parts.append("、".join(f"{item_name(k)}×{v}" for k, v in rw["drops"].items()))
        lines.append("🎁 战利品：" + "，".join(parts))
    else:
        lines.append("道友力有不逮，铩羽而归（无损失，养精蓄锐再来）。")
    lines.append(f"⚡ 精力余 {res['stamina_left']}")
    return "\n".join(lines)


@router.message(Command("explore"))
async def cmd_explore(message: Message):
    if await guard_private_message(message):
        return
    text, markup = await render_menu(message.from_user.id)
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "nav:explore")
async def cb_explore_menu(callback: CallbackQuery):
    if await guard_private_callback(callback):
        return
    text, markup = await render_menu(callback.from_user.id)
    await show(callback, text, markup)
    await callback.answer()


@router.callback_query(F.data.startswith("ex:"))
async def cb_explore_go(callback: CallbackQuery):
    if await guard_private_callback(callback):
        return
    action = await consume_action_callback(callback)
    if not action or not action.startswith("ex:"):
        return
    map_key = action[3:]
    res = await explore_service.explore(callback.from_user.id, map_key)
    markup = await _after_markup(callback.from_user.id, map_key) if res["status"] == "ok" else main_menu()
    await show(callback, _result_text(res), markup)
    await callback.answer()
