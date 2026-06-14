"""闭关：开始 / 出关收功（惰性结算修为）。"""
from __future__ import annotations

import time

from config import realms as R
from services import character, settle


async def start(user_id: int) -> dict:
    char = await character.get(user_id)
    if char.seclusion_at:
        return {"status": "already"}
    await character.set_seclusion(user_id, int(time.time()))
    return {"status": "started"}


async def collect(user_id: int) -> dict:
    char = await character.get(user_id)
    if not char.seclusion_at:
        return {"status": "not_in"}
    now = int(time.time())
    gained = settle.seclusion_gain(char.realm, char.seclusion_at, now, char.root_bone)
    new_cult = char.cultivation + gained
    await character.set_seclusion(user_id, None)
    await character.set_cultivation(user_id, new_cult)
    cost = R.advance_cost(char.realm, char.stage)
    return {"status": "collected", "gained": gained, "cultivation": new_cult,
            "cost": cost, "can_advance": new_cult >= cost,
            "minutes": max(0, (now - char.seclusion_at) // 60)}
