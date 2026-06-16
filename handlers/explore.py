"""/explore —— 选图历练 + 战斗结算。"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, Message)

from config import realms as R
from config.items import item_name
from config.maps import lower_maps, maps_at_realm
from handlers.common import (NEED_START, guard_private_callback, guard_private_message,
                             action_callback_data, consume_action_callback, main_menu, show)
from services import character
from services import explore as explore_service

router = Router()


async def _map_button(user_id: int, key: str, m: dict) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=f"{m['name']}·{m['difficulty']}（精力{m['stamina']}）",
        callback_data=await action_callback_data(user_id, f"ex:{key}"))


async def render_menu(user_id: int, show_lower: bool = False):
    char = await character.get(user_id)
    if not char:
        return NEED_START, None
    active = await explore_service.active_run(user_id)
    if active:
        rows = [[InlineKeyboardButton(
            text="领取结算" if active["status"] == "ready" else "刷新进度",
            callback_data=await action_callback_data(user_id, "ex:collect"))]]
        rows += main_menu().inline_keyboard
        if active["status"] == "ready":
            text = f"⚔️ {active['map']} 历练已完成，可领取结算。"
        else:
            text = f"⚔️ 正在 {active['map']} 历练，约 {_minutes(active['remaining'])} 后归来。"
        return text, InlineKeyboardMarkup(inline_keyboard=rows)
    welfare = await character.sect_welfare(user_id)
    cap = R.STAMINA_CAP[char.realm] + welfare["stamina_bonus"]
    rows = []
    if show_lower:
        for key, m in lower_maps(char.realm):
            rows.append([await _map_button(user_id, key, m)])
        rows.append([InlineKeyboardButton(text="⬅️ 返回当前境界", callback_data="nav:explore")])
        header = "📜 低阶历练（刷低阶材料 / 补突破资源）："
    else:
        for key, m in maps_at_realm(char.realm):
            rows.append([await _map_button(user_id, key, m)])
        if lower_maps(char.realm):
            rows.append([InlineKeyboardButton(
                text="📜 低阶历练", callback_data="nav:explore:lower")])
        header = "本境界三处历练之地（易 / 中 / 难），择一斩妖夺宝："
    rows += main_menu().inline_keyboard
    text = f"⚔️ 历练\n⚡ 精力 {char.stamina}/{cap}\n{header}"
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


async def _after_markup(user_id: int, map_key: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(
        text="🔁 再历练一次",
        callback_data=await action_callback_data(user_id, f"ex:{map_key}")),
        InlineKeyboardButton(text="⚔️ 换地图", callback_data="nav:explore")]]
    rows += main_menu().inline_keyboard
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _active_markup(user_id: int) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(
        text="领取 / 刷新历练",
        callback_data=await action_callback_data(user_id, "ex:collect"))]]
    rows += main_menu().inline_keyboard
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _minutes(seconds: int) -> str:
    minutes = max(1, (seconds + 59) // 60)
    return f"{minutes} 分钟"


def _result_text(res: dict) -> str:
    s = res["status"]
    if s == "started":
        return (
            f"⚔️ 已前往 {res['map']} 历练，预计 {_minutes(res['seconds'])} 后归来。\n"
            f"⚡ 精力余 {res['stamina_left']}"
        )
    if s == "pending":
        return f"⚔️ 正在 {res['map']} 历练，约 {_minutes(res['remaining'])} 后归来。"
    if s == "ready":
        return f"⚔️ {res['map']} 历练已完成，请领取结算。"
    if s == "no_active":
        return "当前没有正在进行的历练。"
    if s == "locked":
        return f"此地凶险，需修为至 {res['need']} 方可踏足。"
    if s == "in_seclusion":
        return "道友尚在闭关，神游太虚，不可同时外出历练。"
    if s == "busy_dungeon":
        return "道友正在秘境之中，须出秘境后方可外出历练。"
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


@router.callback_query(F.data == "nav:explore:lower")
async def cb_explore_lower(callback: CallbackQuery):
    if await guard_private_callback(callback):
        return
    text, markup = await render_menu(callback.from_user.id, show_lower=True)
    await show(callback, text, markup)
    await callback.answer()


@router.callback_query(F.data.startswith("ex:"))
async def cb_explore_go(callback: CallbackQuery):
    if await guard_private_callback(callback):
        return
    action = await consume_action_callback(callback)
    if not action or not action.startswith("ex:"):
        return
    if action == "ex:collect":
        res = await explore_service.collect(callback.from_user.id)
    else:
        res = await explore_service.start(callback.from_user.id, action[3:])
    if res["status"] == "ok":
        markup = await _after_markup(callback.from_user.id, res["map_key"])
    elif res["status"] in {"started", "pending", "ready"}:
        markup = await _active_markup(callback.from_user.id)
    else:
        markup = main_menu()
    await show(callback, _result_text(res), markup)
    await callback.answer()
