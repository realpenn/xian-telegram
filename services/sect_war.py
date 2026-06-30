"""宗门战据点：轻量积分与据点 buff。"""
from __future__ import annotations

import time

from config import sect_war as CFG
from models import db


def _season(now: int) -> str:
    return time.strftime("%Y-%m", time.localtime(now))


def total_drop_pct(base_drop: float, outpost: dict) -> float:
    """合算掉率加成 = 宗门福利 + 据点（矿脉）drop_pct，封顶 +20%。"""
    return min(0.20, float(base_drop) + float((outpost or {}).get("drop_pct", 0.0)))


def is_open(now: int) -> bool:
    """据点战是否在开放窗口内（周六 20:00–21:00，固定上海时区，跨机器确定）。"""
    lt = time.gmtime(int(now) + CFG.WAR_TZ_OFFSET_SECONDS)
    return (lt.tm_wday == CFG.WAR_WEEKDAY
            and CFG.WAR_START_HOUR <= lt.tm_hour < CFG.WAR_END_HOUR)


async def capture(user_id: int, outpost_key: str, score: int = 10, now: int = None) -> dict:
    now = int(time.time()) if now is None else now
    if outpost_key not in CFG.OUTPOSTS:
        return {"status": "bad_outpost"}
    if not is_open(now):
        return {"status": "closed",
                "weekday": CFG.WAR_WEEKDAY,
                "start_hour": CFG.WAR_START_HOUR, "end_hour": CFG.WAR_END_HOUR}
    async with db.transaction() as conn:
        cur = await conn.execute("SELECT sect_id FROM sect_members WHERE user_id=?", (user_id,))
        member = await cur.fetchone()
        await cur.close()
        if not member:
            return {"status": "not_member"}
        season = _season(now)
        # 复合主键 (sect_id, outpost_key)：一个宗门可同时持有多个据点，各自累计积分。
        await conn.execute(
            "INSERT INTO sect_outposts(sect_id, outpost_key, score, season, updated_at) "
            "VALUES(?,?,?,?,?) "
            "ON CONFLICT(sect_id, outpost_key) DO UPDATE SET score=score+?, season=?, updated_at=?",
            (member["sect_id"], outpost_key, score, season, now, score, season, now))
        return {"status": "ok", "outpost": CFG.OUTPOSTS[outpost_key]["name"], "score": score}


async def bonuses_for_user(user_id: int) -> dict:
    """合并该宗门持有的**所有**据点 buff（多据点并存，各自加成累加）。"""
    rows = await db.fetchall(
        "SELECT o.outpost_key FROM sect_members m JOIN sect_outposts o ON o.sect_id=m.sect_id "
        "WHERE m.user_id=?",
        (user_id,))
    merged: dict = {}
    for row in rows:
        for key, val in CFG.OUTPOSTS.get(row["outpost_key"], {}).get("buff", {}).items():
            merged[key] = merged.get(key, 0.0) + float(val)
    return merged
