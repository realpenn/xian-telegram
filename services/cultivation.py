"""闭关：开始 / 出关收功（惰性结算修为）。"""
from __future__ import annotations

from services import character


async def start(user_id: int) -> dict:
    return await character.start_seclusion(user_id)


async def collect(user_id: int) -> dict:
    return await character.collect_seclusion(user_id)
