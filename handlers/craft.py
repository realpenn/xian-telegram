"""/craft —— 炼丹炼器。"""
from __future__ import annotations

import time

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config.items import item_name
from config.recipes import RECIPES, recipes_for_realm
from handlers.common import NEED_START, guard_private_callback, guard_private_message, main_menu, show
from services import character, crafting

router = Router()


async def render_craft(user_id: int):
    char = await character.get(user_id)
    if not char:
        return NEED_START, None
    collected = await crafting.collect_ready(user_id)
    active = await crafting.active_job(user_id)
    lines = ["💊 炼丹炼器"]
    if collected:
        lines.append("出炉：" + "、".join(
            f"{c['name']}×{c.get('qty', 1)}" for c in collected))
    rows = []
    if active:
        recipe = RECIPES[active["recipe_key"]]
        remain = max(0, active["finish_at"] - int(time.time()))
        lines.append(f"炉中：{recipe['name']}，尚需 {remain} 秒。")
        rows.append([InlineKeyboardButton(text="🪙 灵石加速", callback_data="craft:fast")])
    else:
        lines.append("选择一张丹方或图纸下炉：")
        for key, recipe in recipes_for_realm(char.realm):
            mats = "、".join(f"{item_name(k)}×{v}" for k, v in recipe["materials"].items())
            rows.append([InlineKeyboardButton(
                text=f"{recipe['name']}（{mats} / 🪙{recipe['stone']}）",
                callback_data=f"craft:start:{key}")])
    rows += main_menu().inline_keyboard
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


def _result_text(res: dict) -> str:
    s = res["status"]
    if s == "started":
        return f"炉火已起，开始炼制「{res['name']}」，约 {res['seconds']} 秒后出炉。"
    if s == "busy":
        return "炉中已有造化，且待出炉。"
    if s == "locked":
        return "炼丹炼器需筑基后方可稳控炉火。"
    if s == "in_seclusion":
        return "道友闭关中，不宜分神开炉。"
    if s == "no_stone":
        return f"灵石不足（需 {res['need']}，余 {res['have']}）。"
    if s == "no_material":
        return f"材料不足：{item_name(res['item'])} 需 {res['need']}，现有 {res['have']}。"
    if s == "accelerated":
        names = "、".join(c["name"] for c in res["collected"]) or "炉火已催至将成"
        return f"消耗灵石 {res['cost']} 加速，{names}。"
    if s == "no_job":
        return "炉中空空，尚无可加速之物。"
    return "天机紊乱，炉火暂熄。"


@router.message(Command("craft"))
async def cmd_craft(message: Message):
    if await guard_private_message(message):
        return
    text, markup = await render_craft(message.from_user.id)
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "nav:craft")
async def cb_craft(callback: CallbackQuery):
    if await guard_private_callback(callback):
        return
    text, markup = await render_craft(callback.from_user.id)
    await show(callback, text, markup)
    await callback.answer()


@router.callback_query(F.data.startswith("craft:start:"))
async def cb_craft_start(callback: CallbackQuery):
    if await guard_private_callback(callback):
        return
    res = await crafting.start_job(callback.from_user.id, callback.data.split(":", 2)[2])
    await show(callback, _result_text(res), main_menu())
    await callback.answer()


@router.callback_query(F.data == "craft:fast")
async def cb_craft_fast(callback: CallbackQuery):
    if await guard_private_callback(callback):
        return
    res = await crafting.accelerate(callback.from_user.id)
    await show(callback, _result_text(res), main_menu())
    await callback.answer()
