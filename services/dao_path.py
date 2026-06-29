"""道途：元婴起的专修长线。"""
from __future__ import annotations

import time

from config import dao_paths as CFG
from models import db


async def list_paths(user_id: int) -> list[dict]:
    rows = await db.fetchall(
        "SELECT * FROM dao_paths WHERE user_id=? ORDER BY active DESC, unlocked_at, path_key",
        (user_id,))
    return [_format_row(row) for row in rows]


async def active_path(user_id: int):
    row = await db.fetchone(
        "SELECT * FROM dao_paths WHERE user_id=? AND active=1 LIMIT 1",
        (user_id,))
    return _format_row(row) if row else None


async def active_bonuses(user_id: int) -> dict:
    row = await db.fetchone(
        "SELECT path_key, rank FROM dao_paths WHERE user_id=? AND active=1 LIMIT 1",
        (user_id,))
    if not row:
        return {}
    return CFG.bonuses_for(row["path_key"], row["rank"])


async def unlock(user_id: int, path_key: str, now: int = None) -> dict:
    now = int(time.time()) if now is None else now
    if path_key not in CFG.DAO_PATHS:
        return {"status": "bad_path"}
    async with db.transaction() as conn:
        cur = await conn.execute("SELECT realm, stage FROM characters WHERE user_id=?", (user_id,))
        char = await cur.fetchone()
        await cur.close()
        if not char:
            return {"status": "missing"}
        if char["realm"] < CFG.UNLOCK_REALM:
            return {"status": "locked", "need_realm": CFG.UNLOCK_REALM}
        cur = await conn.execute(
            "SELECT 1 FROM dao_paths WHERE user_id=? AND path_key=?",
            (user_id, path_key))
        exists = await cur.fetchone()
        await cur.close()
        if exists:
            await _set_active(conn, user_id, path_key)
            return {"status": "active", "path": CFG.path_name(path_key)}
        cur = await conn.execute("SELECT COUNT(*) AS n FROM dao_paths WHERE user_id=?", (user_id,))
        count = (await cur.fetchone())["n"]
        await cur.close()
        if count > 0:
            return {"status": "need_switch", "path": CFG.path_name(path_key)}
        await conn.execute(
            "INSERT INTO dao_paths(user_id, path_key, xp, rank, active, unlocked_at) "
            "VALUES(?,?,0,0,1,?)",
            (user_id, path_key, now))
        await conn.execute(
            "INSERT INTO path_events(user_id, path_key, event_type, amount, created_at) "
            "VALUES(?,?,?,0,?)",
            (user_id, path_key, "unlock", now))
        return {"status": "unlocked", "path": CFG.path_name(path_key), "rank": 0,
                "rank_name": CFG.rank_name(0)}


async def _set_active(conn, user_id: int, path_key: str):
    await conn.execute("UPDATE dao_paths SET active=0 WHERE user_id=?", (user_id,))
    await conn.execute(
        "UPDATE dao_paths SET active=1 WHERE user_id=? AND path_key=?",
        (user_id, path_key))


def _format_row(row) -> dict:
    return {
        "user_id": row["user_id"],
        "path_key": row["path_key"],
        "name": CFG.path_name(row["path_key"]),
        "xp": row["xp"],
        "rank": row["rank"],
        "rank_name": CFG.rank_name(row["rank"]),
        "active": bool(row["active"]),
        "unlocked_at": row["unlocked_at"],
        "bonuses": CFG.bonuses_for(row["path_key"], row["rank"]),
    }
