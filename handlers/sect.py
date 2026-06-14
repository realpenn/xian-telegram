"""/sect —— 宗门。"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config.items import item_name
from config.sects import CREATE_STONE_COST, SECT_SHOP, upgrade_cost
from handlers.common import (NEED_START, action_callback_data, consume_action_callback,
                             main_menu, show)
from services import sect

router = Router()


async def render_sect(user_id: int):
    mine = await sect.my_sect(user_id)
    rows = []
    if not mine:
        text = (
            "⛩️ 宗门\n"
            f"筑基后可耗灵石 {CREATE_STONE_COST} 创建宗门。\n"
            "用法：/sect create 宗门名，或 /sect join 宗门名。"
        )
    else:
        members = await sect.members(mine["id"])
        lines = [
            f"⛩️ {mine['name']} · Lv.{mine['level']}",
            f"身份：{mine['role']}　贡献：{mine['contribution']}",
            f"宗门贡献池：{mine['contribution_pool']}",
            "—— 门人 ——",
        ]
        lines += [f"{m['role']} {m['username'] or m['user_id']} · 贡献 {m['contribution']}" for m in members]
        text = "\n".join(lines)
        rows.append([InlineKeyboardButton(
            text="📜 宗门任务",
            callback_data=await action_callback_data(user_id, "sect:task"))])
        if mine["role"] == "宗主":
            rows.append([InlineKeyboardButton(
                text=f"⬆️ 升级宗门（贡献池 {upgrade_cost(mine['level'])}）",
                callback_data=await action_callback_data(user_id, "sect:upgrade"))])
        rows.append([InlineKeyboardButton(text="🏪 宗门商店", callback_data="sect:shop")])
    rows += main_menu().inline_keyboard
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def _result_text(res: dict) -> str:
    s = res["status"]
    if s == "ok" and "contribution" in res:
        return f"宗门任务完成，贡献 +{res['contribution']}，灵石 +{res['stone']}。"
    if s == "ok" and "item" in res:
        return f"兑换 {res['item']}×{res['qty']}，消耗贡献 {res['cost']}。"
    if s == "upgraded":
        return f"宗门「{res['name']}」升至 Lv.{res['level']}，消耗贡献池 {res['cost']}。"
    if s == "ok" and "name" in res:
        return f"已入宗门「{res['name']}」。"
    if s == "ok":
        return "宗门事务已办妥。"
    if s == "locked":
        return "需筑基后方可创建宗门。"
    if s == "no_stone":
        return f"灵石不足（需 {res['need']}，余 {res['have']}）。"
    if s == "already_member":
        return "道友已有宗门。"
    if s == "name_taken":
        return "此宗门名已被占用。"
    if s == "not_found":
        return "未寻得此宗门。"
    if s == "not_member":
        return "道友尚未加入宗门。"
    if s == "done":
        return "今日宗门任务已完成。"
    if s == "leader_has_members":
        return "宗主尚有门人在宗，不可独自离去。"
    if s == "no_contribution":
        return f"贡献不足（需 {res['need']}，现有 {res['have']}）。"
    if s == "no_pool":
        return f"宗门贡献池不足（需 {res['need']}，现有 {res['have']}）。"
    if s == "no_permission":
        return "只有宗主可升级宗门。"
    if s == "missing":
        return NEED_START
    return "宗门事务未成。"


@router.message(Command("sect"))
async def cmd_sect(message: Message):
    parts = message.text.split(maxsplit=2)
    if len(parts) >= 3 and parts[1] == "create":
        res = await sect.create(message.from_user.id, parts[2])
        await message.answer(_result_text(res))
        return
    if len(parts) >= 3 and parts[1] == "join":
        res = await sect.join(message.from_user.id, parts[2])
        await message.answer(_result_text(res))
        return
    if len(parts) >= 2 and parts[1] == "task":
        await message.answer(_result_text(await sect.task(message.from_user.id)))
        return
    if len(parts) >= 2 and parts[1] == "leave":
        await message.answer(_result_text(await sect.leave(message.from_user.id)))
        return
    if len(parts) >= 2 and parts[1] == "upgrade":
        await message.answer(_result_text(await sect.upgrade(message.from_user.id)))
        return
    if len(parts) >= 3 and parts[1] == "buy":
        await message.answer(_result_text(await sect.redeem(message.from_user.id, parts[2])))
        return
    text, markup = await render_sect(message.from_user.id)
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "nav:sect")
async def cb_sect(callback: CallbackQuery):
    text, markup = await render_sect(callback.from_user.id)
    await show(callback, text, markup)
    await callback.answer()


@router.callback_query(F.data.startswith("sect:task:"))
async def cb_task(callback: CallbackQuery):
    if await consume_action_callback(callback) != "sect:task":
        return
    await show(callback, _result_text(await sect.task(callback.from_user.id)), main_menu())
    await callback.answer()


@router.callback_query(F.data.startswith("sect:upgrade:"))
async def cb_upgrade(callback: CallbackQuery):
    if await consume_action_callback(callback) != "sect:upgrade":
        return
    await show(callback, _result_text(await sect.upgrade(callback.from_user.id)), main_menu())
    await callback.answer()


@router.callback_query(F.data == "sect:shop")
async def cb_shop(callback: CallbackQuery):
    rows = [
        [InlineKeyboardButton(
            text=f"{item_name(key)}（贡献 {good['contribution']}）",
            callback_data=await action_callback_data(callback.from_user.id, f"sect:buy:{key}"))]
        for key, good in SECT_SHOP.items()
    ]
    rows += main_menu().inline_keyboard
    await show(callback, "🏪 宗门商店", InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data.startswith("sect:buy:"))
async def cb_buy(callback: CallbackQuery):
    action = await consume_action_callback(callback)
    if not action or not action.startswith("sect:buy:"):
        return
    key = action.split(":", 2)[2]
    await show(callback, _result_text(await sect.redeem(callback.from_user.id, key)), main_menu())
    await callback.answer()
