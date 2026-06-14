"""/rank —— 天梯排行榜。"""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from services import pvp

router = Router()


@router.message(Command("rank"))
async def cmd_rank(message: Message):
    rows = await pvp.top()
    if not rows:
        await message.answer("天梯尚无名次，先来一场 /pvp。")
        return
    lines = ["🏆 天梯排行榜"]
    for idx, row in enumerate(rows, 1):
        name = row["username"] or str(row["user_id"])
        lines.append(
            f"{idx}. {name} · {pvp.tier(row['rating'])} {row['rating']} 分 "
            f"· 声望 {row['reputation']} ({row['wins']}胜/{row['losses']}负)")
    await message.answer("\n".join(lines))
