"""/weekly —— 周活动副本。"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import time

from config import weekly_events as CFG
from config.items import item_name
from handlers.common import (NEED_START, action_callback_data, append_main_menu_return,
                             consume_action_callback, guard_private_callback,
                             guard_private_message, section_back_markup, show)
from services import character, weekly_events

router = Router()


async def render_weekly(user_id: int):
    char = await character.get(user_id)
    if not char:
        return NEED_START, None
    open_key = weekly_events.current_theme_key(int(time.time()))
    theme = CFG.WEEKLY_THEMES[open_key]
    lines = [
        "🗓️ 周活动副本",
        f"每次消耗精力 {CFG.RUN_STAMINA_COST}，绑定材料 ×1；道行每周上限 {CFG.WEEKLY_DAOHANG_CAP}。",
        f"本周开放：{theme['name']}（产出 {item_name(theme['material'])}，绑定）",
        f"当前精力：{char.stamina}",
    ]
    rows = [[InlineKeyboardButton(
        text=f"挑战 {theme['name']}",
        callback_data=await action_callback_data(user_id, f"weekly:run:{open_key}"))]]
    lines.append("—— 活动商店（消耗活动材料，均为绑定）——")
    for key, offer in CFG.SHOP_OFFERS.items():
        lines.append(f"{offer['name']} ×{offer['reward_qty']}：{offer['material_cost']} 活动材料")
        rows.append([InlineKeyboardButton(
            text=f"兑换 {offer['name']}（{offer['material_cost']} 材料）",
            callback_data=await action_callback_data(user_id, f"weekly:shop:{key}"))])
    append_main_menu_return(rows)
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


def _result_text(res: dict) -> str:
    s = res["status"]
    if s == "ok" and res.get("kind") == "ascension":
        return f"兑换成功，消耗 {res['cost']} 活动材料，获得飞升点 +{res['qty']}。"
    if s == "ok" and res.get("kind") == "item":
        return f"兑换成功，消耗 {res['cost']} 活动材料，获得 {item_name(res['item'])} ×{res['qty']}（绑定）。"
    if s == "ok":
        bound = "绑定" if res.get("bound") else "非绑定"
        return f"{res['theme']} 完成，获道行 +{res['daohang']}，{item_name(res['material'])} ×1（{bound}）。"
    if s == "no_material":
        return f"活动材料不足（需 {res['need']}，现有 {res['have']}）。"
    if s == "bad_offer":
        return "暂无此兑换。"
    if s == "no_stamina":
        return f"精力不足（需 {res['need']}，现有 {res['have']}）。"
    if s == "closed":
        return f"本周开放的是「{res['open_name']}」，该活动暂未开放。"
    if s == "bad_theme":
        return "暂无此活动。"
    if s == "missing":
        return NEED_START
    return "活动未成。"


@router.message(Command("weekly"))
async def cmd_weekly(message: Message):
    if await guard_private_message(message):
        return
    text, markup = await render_weekly(message.from_user.id)
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "nav:weekly")
async def cb_weekly(callback: CallbackQuery):
    if await guard_private_callback(callback):
        return
    text, markup = await render_weekly(callback.from_user.id)
    await show(callback, text, markup)
    await callback.answer()


@router.callback_query(F.data.startswith("weekly:run:"))
async def cb_weekly_run(callback: CallbackQuery):
    if await guard_private_callback(callback):
        return
    action = await consume_action_callback(callback)
    if not action or not action.startswith("weekly:run:"):
        return
    res = await weekly_events.run(callback.from_user.id, action.rsplit(":", 1)[1])
    await show(callback, _result_text(res), section_back_markup("↩️ 返回活动", "nav:weekly"))
    await callback.answer()


@router.callback_query(F.data.startswith("weekly:shop:"))
async def cb_weekly_shop(callback: CallbackQuery):
    if await guard_private_callback(callback):
        return
    action = await consume_action_callback(callback)
    if not action or not action.startswith("weekly:shop:"):
        return
    res = await weekly_events.exchange(callback.from_user.id, action.rsplit(":", 1)[1])
    await show(callback, _result_text(res), section_back_markup("↩️ 返回活动", "nav:weekly"))
    await callback.answer()
