"""/cultivate —— 闭关 / 出关；以及突破回调 bt:do。"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from handlers.common import NEED_START, main_menu, menu_with_breakthrough, show
from services import breakthrough, character, cultivation

router = Router()


async def do_cultivate(user_id: int):
    char = await character.get(user_id)
    if not char:
        return NEED_START, None
    if char.seclusion_at:
        res = await cultivation.collect(user_id)
        lines = [f"🧘 出关！闭关 {res['minutes']} 分钟，修为精进 +{res['gained']}。",
                 f"修为 {res['cultivation']}/{res['cost']}"]
        if res["can_advance"]:
            lines.append("✨ 修为已足，可尝试突破！")
        return "\n".join(lines), menu_with_breakthrough(res["can_advance"])
    await cultivation.start(user_id)
    text = ("🧘 道友盘膝而坐，敛息凝神，开始闭关参悟……\n"
            "（修为随时间累积，离线上限 12 时辰。再用一次 /cultivate 或点「闭关」即出关收功。）")
    return text, main_menu()


def _bt_text(res: dict) -> str:
    s = res["status"]
    if s == "need_cult":
        return f"修为尚浅，还差 {res['need']} 方可冲关。且去闭关或历练。"
    if s == "at_cap":
        return "道友已臻元婴圆满，乃此界之绝巅（化神之境，留待来日开启）。"
    if s == "need_pill":
        return f"大境界突破需「{res['pill']}」护道，道友尚缺此物。"
    if s == "small_success":
        return f"📈 水到渠成，道友晋入 {res['label']}！"
    if s == "big_success":
        if res["tribulation"]:
            return f"⚡ 天劫加身，雷光淬体——道友力扛三道天雷，破境而出，臻至 {res['label']}！"
        return f"✨ 灵气灌顶，道友冲破桎梏，迈入 {res['label']}！"
    if s == "big_fail":
        head = "⚡ 天劫凶猛" if res["tribulation"] else "✗ 冲关受阻"
        return f"{head}，道友未能破境，道基微损（修为 −{res['loss']}），所幸未曾跌境。来日再战。"
    return "天机紊乱，突破未果。"


@router.message(Command("cultivate"))
async def cmd_cultivate(message: Message):
    text, markup = await do_cultivate(message.from_user.id)
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "nav:cultivate")
async def cb_cultivate(callback: CallbackQuery):
    text, markup = await do_cultivate(callback.from_user.id)
    await show(callback, text, markup)
    await callback.answer()


@router.callback_query(F.data == "bt:do")
async def cb_breakthrough(callback: CallbackQuery):
    res = await breakthrough.try_advance(callback.from_user.id)
    await show(callback, _bt_text(res), main_menu())
    await callback.answer()
