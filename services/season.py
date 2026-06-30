"""月赛季奖励：绑定称号 + 少量道行。"""
from __future__ import annotations

import time

from models import db

SEASON_DAOHANG_REWARD = 80
SEASON_TITLE = "赛季英杰"


def _season(now: int) -> str:
    return time.strftime("%Y-%m", time.localtime(now))


async def claim(user_id: int, now: int = None) -> dict:
    now = int(time.time()) if now is None else now
    season = _season(now)
    async with db.transaction() as conn:
        cur = await conn.execute("SELECT 1 FROM characters WHERE user_id=?", (user_id,))
        ch = await cur.fetchone()
        await cur.close()
        if not ch:
            return {"status": "missing"}
        cur = await conn.execute(
            "SELECT 1 FROM pvp_season_rewards WHERE user_id=? AND season=?",
            (user_id, season))
        exists = await cur.fetchone()
        await cur.close()
        if exists:
            return {"status": "claimed"}
        await conn.execute(
            "UPDATE characters SET daohang=daohang+? WHERE user_id=?",
            (SEASON_DAOHANG_REWARD, user_id))
        await conn.execute(
            "INSERT INTO pvp_season_rewards(user_id, season, title, daohang, claimed_at) "
            "VALUES(?,?,?,?,?)",
            (user_id, season, SEASON_TITLE, SEASON_DAOHANG_REWARD, now))
        return {"status": "ok", "title": SEASON_TITLE, "daohang": SEASON_DAOHANG_REWARD}


async def settle_monthly(now: int = None) -> list:
    """月末赛季结算：仅向参与过天梯（有胜负记录）的玩家发放绑定称号 + 道行。

    幂等：复用 claim 的 `pvp_season_rewards` 唯一键，重复结算不重复发放。
    由 scheduler 在月末触发（见 bot/app.py）。
    """
    now = int(time.time()) if now is None else now
    rows = await db.fetchall(
        "SELECT user_id FROM pvp_ratings WHERE wins + losses > 0")
    granted = []
    for row in rows:
        res = await claim(row["user_id"], now)
        if res.get("status") == "ok":
            granted.append(row["user_id"])
    return granted
