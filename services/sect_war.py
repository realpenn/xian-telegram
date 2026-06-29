"""宗门战据点：轻量积分与据点 buff。"""
from __future__ import annotations

import time

from config import sect_war as CFG
from models import db


def _season(now: int) -> str:
    return time.strftime("%Y-%m", time.localtime(now))


async def capture(user_id: int, outpost_key: str, score: int = 10, now: int = None) -> dict:
    now = int(time.time()) if now is None else now
    if outpost_key not in CFG.OUTPOSTS:
        return {"status": "bad_outpost"}
    async with db.transaction() as conn:
        cur = await conn.execute("SELECT sect_id FROM sect_members WHERE user_id=?", (user_id,))
        member = await cur.fetchone()
        await cur.close()
        if not member:
            return {"status": "not_member"}
        season = _season(now)
        await conn.execute(
            "INSERT INTO sect_outposts(sect_id, outpost_key, score, season, updated_at) "
            "VALUES(?,?,?,?,?) "
            "ON CONFLICT(sect_id) DO UPDATE SET outpost_key=?, score=score+?, season=?, updated_at=?",
            (member["sect_id"], outpost_key, score, season, now, outpost_key, score, season, now))
        return {"status": "ok", "outpost": CFG.OUTPOSTS[outpost_key]["name"], "score": score}


async def bonuses_for_user(user_id: int) -> dict:
    row = await db.fetchone(
        "SELECT o.outpost_key FROM sect_members m JOIN sect_outposts o ON o.sect_id=m.sect_id "
        "WHERE m.user_id=?",
        (user_id,))
    if not row:
        return {}
    return dict(CFG.OUTPOSTS.get(row["outpost_key"], {}).get("buff", {}))
