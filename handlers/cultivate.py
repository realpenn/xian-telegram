"""/cultivate —— 闭关 / 出关；以及突破回调 bt:do。"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from handlers.common import (NEED_START, guard_private_callback, guard_private_message,
                             action_callback_data, consume_action_callback, main_menu,
                             menu_with_breakthrough, show)
from services import breakthrough, character, cultivation

router = Router()


async def do_cultivate(user_id: int):
    char = await character.get(user_id)
    if not char:
        return NEED_START, None
    if char.seclusion_at:
        res = await cultivation.collect(user_id)
        if res["status"] != "collected":
            return "闭关状态已变，请稍后再试。", main_menu()
        lines = [f"🧘 出关！闭关 {res['minutes']} 分钟，修为精进 +{res['gained']}。",
                 f"修为 {res['cultivation']}/{res['cost']}"]
        if res["can_advance"]:
            lines.append("✨ 修为已足，可尝试突破！")
        return "\n".join(lines), await menu_with_breakthrough(user_id, res["can_advance"])
    await cultivation.start(user_id)
    text = ("🧘 道友盘膝而坐，敛息凝神，开始闭关参悟……\n"
            "（修为随时间累积，离线上限 12 时辰。再用一次 /cultivate 或点「闭关」即出关收功。）")
    return text, main_menu()


async def render_cultivate(user_id: int):
    char = await character.get(user_id)
    if not char:
        return NEED_START, None
    if char.seclusion_at:
        text = "🧘 道友正在闭关。若要收功出关，请点下方按钮。"
        button = "出关收功"
    else:
        text = "🧘 洞府清净，可入定闭关，离线积攒修为。"
        button = "开始闭关"
    rows = [[InlineKeyboardButton(
        text=button,
        callback_data=await action_callback_data(user_id, "cult:toggle"))]]
    rows += main_menu().inline_keyboard
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def _bt_text(res: dict) -> str:
    s = res["status"]
    if s == "need_cult":
        return f"修为尚浅，还差 {res['need']} 方可冲关。且去闭关或历练。"
    if s == "in_seclusion":
        return "道友仍在闭关，不宜分心冲关。且先出关收功。"
    if s == "missing":
        return NEED_START
    if s == "at_cap":
        return "道友已臻元婴圆满，乃此界之绝巅（化神之境，留待来日开启）。"
    if s == "need_pill":
        return f"大境界突破需「{res['pill']}」护道，道友尚缺此物。"
    if s == "small_success":
        return f"📈 水到渠成，道友晋入 {res['label']}！"
    if s == "big_success":
        tail = "\n" + "\n".join(res.get("tribulation_log", [])) if res.get("tribulation_log") else ""
        if res["tribulation"]:
            return f"⚡ 天劫加身，雷光淬体——道友力扛三道天雷，破境而出，臻至 {res['label']}！{tail}"
        return f"✨ 灵气灌顶，道友冲破桎梏，迈入 {res['label']}！"
    if s == "big_fail":
        head = "⚡ 天劫凶猛" if res["tribulation"] else "✗ 冲关受阻"
        tail = "\n" + "\n".join(res.get("tribulation_log", [])) if res.get("tribulation_log") else ""
        return (
            f"{head}，道友未能破境，道基不稳（修为 −{res['loss']}，"
            f"法身六维暂降），所幸未曾跌境。来日再战。{tail}"
        )
    return "天机紊乱，突破未果。"


@router.message(Command("cultivate"))
async def cmd_cultivate(message: Message):
    if await guard_private_message(message):
        return
    text, markup = await do_cultivate(message.from_user.id)
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "nav:cultivate")
async def cb_cultivate(callback: CallbackQuery):
    if await guard_private_callback(callback):
        return
    text, markup = await render_cultivate(callback.from_user.id)
    await show(callback, text, markup)
    await callback.answer()


@router.callback_query(F.data.startswith("cult:toggle:"))
async def cb_cultivate_toggle(callback: CallbackQuery):
    if await guard_private_callback(callback):
        return
    if await consume_action_callback(callback) != "cult:toggle":
        return
    text, markup = await do_cultivate(callback.from_user.id)
    await show(callback, text, markup)
    await callback.answer()


@router.callback_query(F.data.startswith("bt:do:"))
async def cb_breakthrough(callback: CallbackQuery):
    if await guard_private_callback(callback):
        return
    if await consume_action_callback(callback) != "bt:do":
        return
    res = await breakthrough.try_advance(callback.from_user.id)
    await show(callback, _bt_text(res), main_menu())
    await callback.answer()
