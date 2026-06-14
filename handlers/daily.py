"""/daily —— 每日签到。"""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from handlers.common import NEED_START
from services import daily

router = Router()


@router.message(Command("daily"))
async def cmd_daily(message: Message):
    res = await daily.checkin(message.from_user.id)
    if res["status"] == "ok":
        await message.answer(f"📅 签到成功，连续 {res['streak']} 日，灵石 +{res['stone']}。")
    elif res["status"] == "missing":
        await message.answer(NEED_START)
    else:
        await message.answer(f"今日已签到，连续 {res['streak']} 日。")
