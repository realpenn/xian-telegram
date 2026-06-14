"""/pvp —— 群内切磋 / 天梯。"""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from handlers.common import NEED_START, is_private_chat
from services import pvp

router = Router()


def _name(user) -> str:
    return user.username or user.full_name or str(user.id)


def _text(res: dict, opponent_name: str = "对手") -> str:
    s = res["status"]
    if s == "ok":
        shown = res["log"] if len(res["log"]) <= 8 else (res["log"][:7] + ["……", res["log"][-1]])
        return "\n".join([
            f"⚔️ 切磋：道友 vs {opponent_name}",
            *shown,
            f"{'技高一筹' if res['win'] else '惜败半招'}，天梯积分 {res['rating_delta']:+d}。",
        ])
    if s == "no_opponent":
        return "暂未寻得合适对手。可让另一位道友先 /start。"
    if s == "daily_limit":
        return f"今日切磋已满 {res['limit']} 次。"
    if s == "in_seclusion":
        return "道友仍在闭关，不可切磋。"
    if s == "opponent_busy":
        return "对方闭关中，不便应战。"
    if s == "realm_gap":
        return "境界相差过大，此战不合天梯规矩。"
    if s == "missing":
        return NEED_START
    if s == "self":
        return "与己切磋，剑意无所落处。"
    return "切磋未成。"


@router.message(Command("pvp"))
async def cmd_pvp(message: Message):
    if is_private_chat(message.chat):
        await message.answer("切磋与天梯请在群中进行。")
        return
    opponent_id = None
    opponent_name = "随机对手"
    if message.reply_to_message and message.reply_to_message.from_user:
        opponent = message.reply_to_message.from_user
        opponent_id = opponent.id
        opponent_name = _name(opponent)
    res = await pvp.duel(message.from_user.id, opponent_id)
    await message.answer(_text(res, opponent_name))
