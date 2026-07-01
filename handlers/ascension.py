"""/ascension —— 飞升试炼与账号级被动。"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import ascension as CFG
from handlers.common import (NEED_START, action_callback_data, append_main_menu_return,
                             button_grid, consume_action_callback,
                             guard_private_callback, guard_private_message,
                             section_back_markup, show)
from services import ascension, character

router = Router()


async def render_ascension(user_id: int):
    char = await character.get(user_id)
    if not char:
        return NEED_START, None
    state = await ascension.get(user_id)
    spent = state.get("spent", {})
    title = CFG.ascension_title(state["level"])
    title_line = f"　尊号：「{title}」" if title else ""
    lines = [
        "🌌 飞升",
        f"飞升点：{state['points']}　总阶：{state['level']}{title_line}　道行：{char.daohang}",
        f"飞升试炼：化神圆满可挑战，消耗道行 {CFG.TRIAL_DAOHANG_COST}，得飞升点 {CFG.TRIAL_POINT_REWARD}。",
        "—— 被动 ——",
    ]
    buttons = [InlineKeyboardButton(
        text="挑战飞升试炼",
        callback_data=await action_callback_data(user_id, "asc:trial"))]
    for key, name in CFG.PASSIVES.items():
        lvl = int(spent.get(key, 0))
        lines.append(f"{name}：{lvl}/{CFG.PASSIVE_CAP}（每级 +1%）")
        if lvl < CFG.PASSIVE_CAP:
            buttons.append(InlineKeyboardButton(
                text=f"升级 {name}",
                callback_data=await action_callback_data(user_id, f"asc:up:{key}")))
    rows = button_grid(buttons)
    append_main_menu_return(rows)
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


def _result_text(res: dict) -> str:
    s = res["status"]
    if s == "ok" and "points" in res:
        return f"飞升试炼成功，消耗道行 {res['cost']}，获得飞升点 {res['points']}。"
    if s == "ok":
        title = res.get("title") or ""
        unlock = f"　尊号「{title}」解锁！" if title else ""
        return f"{res['name']} 被动升至 {res['level']} 级。{unlock}"
    if s == "locked":
        return "化神圆满后方可挑战飞升试炼。"
    if s == "weekly_done":
        return "本周飞升试炼已完成，下周再来。"
    if s == "no_daohang":
        return f"道行不足（需 {res['need']}，现有 {res['have']}）。"
    if s == "no_points":
        return f"飞升点不足（需 {res['need']}，现有 {res['have']}）。"
    if s == "max":
        return f"此被动已达上限 {res['cap']} 级。"
    if s == "bad_passive":
        return "无此飞升被动。"
    if s == "missing":
        return NEED_START
    return "飞升未成。"


@router.message(Command("ascension"))
async def cmd_ascension(message: Message):
    if await guard_private_message(message):
        return
    text, markup = await render_ascension(message.from_user.id)
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "nav:ascension")
async def cb_ascension(callback: CallbackQuery):
    if await guard_private_callback(callback):
        return
    text, markup = await render_ascension(callback.from_user.id)
    await show(callback, text, markup)
    await callback.answer()


@router.callback_query(F.data.startswith("asc:"))
async def cb_ascension_action(callback: CallbackQuery):
    if await guard_private_callback(callback):
        return
    action = await consume_action_callback(callback)
    if not action or not action.startswith("asc:"):
        return
    if action == "asc:trial":
        res = await ascension.trial(callback.from_user.id)
    else:
        res = await ascension.upgrade_passive(callback.from_user.id, action.rsplit(":", 1)[1])
    await show(callback, _result_text(res), section_back_markup("↩️ 返回飞升", "nav:ascension"))
    await callback.answer()
