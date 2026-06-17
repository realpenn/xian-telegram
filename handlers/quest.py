"""/quest —— 每日/周常悬赏与成就。"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from handlers.common import (NEED_START, action_callback_data, consume_action_callback,
                             guard_private_callback, guard_private_message, main_menu, show)
from services import character, quests

router = Router()


async def render_quest(user_id: int):
    if not await character.exists(user_id):
        return NEED_START, None
    state = await quests.list_status(user_id)
    lines = ["📜 悬赏"]
    rows = []
    for q in state["quests"]:
        tag = "日常" if q["period"] == "daily" else "周常"
        suffix = "已领" if q["claimed"] else "可领" if q["ready"] else ""
        lines.append(f"{tag}·{q['name']}：{q['progress']}/{q['target']} {suffix}".rstrip())
        if q["ready"]:
            rows.append([InlineKeyboardButton(
                text=f"领取 {q['name']}",
                callback_data=await action_callback_data(user_id, f"quest:claim:{q['key']}"))])
    if state["achievements"]:
        shown = "、".join(quests.achievement_name(row["key"]) for row in state["achievements"][:5])
        lines.append(f"🏅 成就：{shown}")
    else:
        lines.append("🏅 成就：暂无")
    rows += main_menu().inline_keyboard
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


def _claim_text(res: dict) -> str:
    if res["status"] == "ok":
        return f"📜 悬赏「{res['quest']}」已结，{quests.reward_text(res['reward'])}。"
    if res["status"] == "claimed":
        return "此悬赏已领取。"
    if res["status"] == "not_ready":
        return "悬赏尚未完成。"
    return "查无此悬赏。"


@router.message(Command("quest"))
async def cmd_quest(message: Message):
    if await guard_private_message(message):
        return
    text, markup = await render_quest(message.from_user.id)
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "nav:quest")
async def cb_quest(callback: CallbackQuery):
    if await guard_private_callback(callback):
        return
    text, markup = await render_quest(callback.from_user.id)
    await show(callback, text, markup)
    await callback.answer()


@router.callback_query(F.data.startswith("quest:claim:"))
async def cb_quest_claim(callback: CallbackQuery):
    if await guard_private_callback(callback):
        return
    action = await consume_action_callback(callback)
    if not action or not action.startswith("quest:claim:"):
        return
    res = await quests.claim(callback.from_user.id, action.rsplit(":", 1)[1])
    await show(callback, _claim_text(res), main_menu())
    await callback.answer()
