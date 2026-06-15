"""/bag —— 最简储物袋。"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config.items import is_usable, item_name
from handlers.common import (NEED_START, action_callback_data, consume_action_callback,
                             guard_private_callback, guard_private_message, main_menu, show)
from services import character, items as item_service

router = Router()


async def render_bag(user_id: int):
    char = await character.get(user_id)
    if not char:
        return NEED_START, None
    inv = await character.inventory(user_id)
    instances = await character.item_instances(user_id)
    lines = ["🎒 储物袋", f"🪙 灵石 {char.spirit_stone}"]
    rows = []
    if inv:
        lines.append("—— 物品 ——")
        for key, qty in inv:
            lines.append(f"{item_name(key)} ×{qty}")
            if is_usable(key):
                rows.append([InlineKeyboardButton(
                    text=f"使用 {item_name(key)}",
                    callback_data=await action_callback_data(user_id, f"bag:use:{key}"))])
    if instances:
        lines.append("—— 法宝 ——")
        for inst in instances:
            mark = "已装备" if inst["equipped_slot"] else "未装备"
            lines.append(f"#{inst['id']} {item_name(inst['base_key'])}（{mark}）")
    if not inv and not instances:
        lines.append("（空空如也，去历练寻些机缘吧）")
    rows += main_menu().inline_keyboard
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


def _result_text(res: dict) -> str:
    s = res["status"]
    if s == "stamina_ok":
        suffix = f"（今日 {res.get('nth')}/{res['limit']} 次）" if res.get("limit") else ""
        return f"服下补灵丹，精力 +{res['gain']}（{res['stamina']}/{res['cap']}）。{suffix}"
    if s == "stamina_full":
        return "精力已满，暂不必服用补灵丹。"
    if s == "pill_limit":
        return f"今日补灵丹已服 {res['limit']} 次，灵气紊乱，需待明日。"
    if s == "healed":
        return "服下疗伤丹，道基渐稳。"
    if s == "root_up":
        return f"炼化{res['item']}，根骨 {res['old']} → {res['new']}。"
    if s == "root_cap":
        return f"根骨已臻当前上限 {res['cap']}。"
    if s == "buff_ok":
        minutes = max(1, res["duration"] // 60)
        return f"服下{res['item']}，药力流转，增益持续 {minutes} 分钟。"
    if s == "recipe_ok":
        return f"研读{res['item']}，已掌握「{res['recipe']}」。"
    if s == "known_recipe":
        return f"「{res['recipe']}」早已烂熟于心。"
    if s == "no_item":
        return f"储物袋中没有 {res['item']}。"
    if s == "missing":
        return NEED_START
    return "此物暂不可直接使用。"


@router.message(Command("bag"))
async def cmd_bag(message: Message):
    if await guard_private_message(message):
        return
    text, markup = await render_bag(message.from_user.id)
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "nav:bag")
async def cb_bag(callback: CallbackQuery):
    if await guard_private_callback(callback):
        return
    text, markup = await render_bag(callback.from_user.id)
    await show(callback, text, markup)
    await callback.answer()


@router.callback_query(F.data.startswith("bag:use:"))
async def cb_use_item(callback: CallbackQuery):
    if await guard_private_callback(callback):
        return
    action = await consume_action_callback(callback)
    if not action or not action.startswith("bag:use:"):
        return
    res = await item_service.use(callback.from_user.id, action.split(":", 2)[2])
    await show(callback, _result_text(res), main_menu())
    await callback.answer()
