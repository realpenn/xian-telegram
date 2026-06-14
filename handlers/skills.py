"""/skills —— 法宝与功法配置。"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config.items import ITEMS, equipment_slot, item_name
from config.skills import MIND_SLOT, skill_name
from handlers.common import NEED_START, guard_private_callback, guard_private_message, main_menu, show
from services import character

router = Router()


def _bonus_text(inst: dict) -> str:
    bonus = character.equipment_bonus(inst)
    return "、".join(f"{k}+{v}" for k, v in bonus.items()) or "无词条"


async def render_skills(user_id: int):
    char = await character.get(user_id)
    if not char:
        return NEED_START, None
    mind = await character.get_mind_skill(user_id)
    skills = await character.get_skills(user_id)
    instances = await character.item_instances(user_id)
    inv = await character.inventory(user_id)
    lines = [
        "📖 功法 / 法宝",
        "心法：" + (skill_name(mind) if mind else "无"),
        "战技栏：" + ("、".join(skill_name(s) for s in skills) if skills else "无"),
    ]
    rows = []
    if instances:
        lines.append("—— 法宝 ——")
        for inst in instances:
            mark = "已装备" if inst["equipped_slot"] else "未装备"
            lines.append(f"#{inst['id']} {item_name(inst['base_key'])}（{mark}，{_bonus_text(inst)}）")
            if not inst["equipped_slot"] and equipment_slot(inst["base_key"]):
                rows.append([InlineKeyboardButton(
                    text=f"装备 {item_name(inst['base_key'])}", callback_data=f"equip:{inst['id']}")])
    else:
        lines.append("尚无法宝实例，可由炼器或秘境获得。")

    page_buttons = []
    for key, qty in inv:
        item = ITEMS.get(key, {})
        if item.get("type") == "page" and qty >= item.get("need", 999):
            page_buttons.append([InlineKeyboardButton(
                text=f"领悟 {skill_name(item['skill'])}", callback_data=f"learn:{key}")])
    if page_buttons:
        lines.append("残页已足，可领悟新功法。")
        rows += page_buttons
    rows += main_menu().inline_keyboard
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


def _result_text(res: dict) -> str:
    s = res["status"]
    if s == "ok" and "name" in res:
        return f"已装备 {res['name']}。"
    if s == "ok":
        slot_name = "心法栏" if res.get("slot") == MIND_SLOT else "战技栏"
        return f"已领悟 {skill_name(res['skill'])}，置入{slot_name}。"
    if s == "need_pages":
        return f"残页不足（需 {res['need']}，现有 {res['have']}）。"
    if s == "known":
        return f"{skill_name(res['skill'])} 已在战技栏中。"
    if s == "not_found":
        return "未寻得此法宝。"
    return "天机不明，配置未变。"


@router.message(Command("skills"))
async def cmd_skills(message: Message):
    if await guard_private_message(message):
        return
    text, markup = await render_skills(message.from_user.id)
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "nav:skills")
async def cb_skills(callback: CallbackQuery):
    if await guard_private_callback(callback):
        return
    text, markup = await render_skills(callback.from_user.id)
    await show(callback, text, markup)
    await callback.answer()


@router.callback_query(F.data.startswith("equip:"))
async def cb_equip(callback: CallbackQuery):
    if await guard_private_callback(callback):
        return
    res = await character.equip_instance(callback.from_user.id, int(callback.data[6:]))
    await show(callback, _result_text(res), main_menu())
    await callback.answer()


@router.callback_query(F.data.startswith("learn:"))
async def cb_learn(callback: CallbackQuery):
    if await guard_private_callback(callback):
        return
    res = await character.learn_skill_from_pages(callback.from_user.id, callback.data[6:])
    await show(callback, _result_text(res), main_menu())
    await callback.answer()
