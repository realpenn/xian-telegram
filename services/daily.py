"""每日签到（spec §9/§12 指令表）。"""
from __future__ import annotations

import time

from models import db


def _day(ts: int) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(ts))


async def checkin(user_id: int, now: int = None) -> dict:
    now = int(time.time()) if now is None else now
    day = _day(now)
    async with db.transaction() as conn:
        cur = await conn.execute("SELECT 1 FROM characters WHERE user_id=?", (user_id,))
        char = await cur.fetchone()
        await cur.close()
        if not char:
            return {"status": "missing"}
        cur = await conn.execute("SELECT * FROM daily WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        await cur.close()
        if row and row["last_checkin_day"] == day:
            return {"status": "done", "streak": row["streak"]}
        streak = (row["streak"] + 1) if row else 1
        reward = 80 + min(streak, 7) * 10
        await conn.execute(
            "INSERT INTO daily(user_id, last_checkin_day, streak) VALUES(?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET last_checkin_day=?, streak=?",
            (user_id, day, streak, day, streak))
        await conn.execute(
            "UPDATE characters SET spirit_stone = spirit_stone + ? WHERE user_id=?",
            (reward, user_id))
        return {"status": "ok", "streak": streak, "stone": reward}
