"""前台活动时间窗：用于闭关并行时折算后台收益。"""
from __future__ import annotations

import time

from models import db

SECLUSION_ACTIVE_FACTOR = 0.50
KEEP_SECONDS = 7 * 24 * 3600


async def record_window(user_id: int, kind: str, source_key: str,
                        start_at: int, finish_at: int, conn=None):
    if finish_at <= start_at:
        finish_at = start_at + 1
    sql = (
        "INSERT INTO activity_windows(user_id, kind, source_key, start_at, finish_at) "
        "VALUES(?,?,?,?,?)"
    )
    params = (user_id, kind, source_key, int(start_at), int(finish_at))
    if conn is not None:
        await conn.execute(sql, params)
    else:
        await db.execute(sql, params)


async def record_virtual_window(user_id: int, kind: str, source_key: str,
                                now: int, duration: int, conn=None):
    """扫荡等即时操作仍占用一段后台折算窗口；窗口串行接在玩家最近窗口之后。"""
    start = int(now)
    query = "SELECT MAX(finish_at) AS finish_at FROM activity_windows WHERE user_id=?"
    if conn is not None:
        cur = await conn.execute(query, (user_id,))
        row = await cur.fetchone()
        await cur.close()
    else:
        row = await db.fetchone(query, (user_id,))
    if row and row["finish_at"] and row["finish_at"] > start:
        start = int(row["finish_at"])
    await record_window(user_id, kind, source_key, start, start + max(1, int(duration)), conn=conn)
    return {"start_at": start, "finish_at": start + max(1, int(duration))}


async def windows_for(user_id: int, start_at: int, finish_at: int, conn=None) -> list[tuple[int, int]]:
    sql = (
        "SELECT start_at, finish_at FROM activity_windows "
        "WHERE user_id=? AND finish_at>? AND start_at<? ORDER BY start_at"
    )
    params = (user_id, int(start_at), int(finish_at))
    if conn is not None:
        cur = await conn.execute(sql, params)
        rows = await cur.fetchall()
        await cur.close()
    else:
        rows = await db.fetchall(sql, params)
    return [(int(row["start_at"]), int(row["finish_at"])) for row in rows]


async def cleanup(now: int = None):
    now = int(time.time()) if now is None else now
    await db.execute("DELETE FROM activity_windows WHERE finish_at<?", (now - KEEP_SECONDS,))
