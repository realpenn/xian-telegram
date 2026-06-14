"""宗门系统（spec §11）。"""
from __future__ import annotations

import time

from config.items import item_name
from config.sects import CREATE_REALM, CREATE_STONE_COST, SECT_SHOP, TASK_CONTRIBUTION, TASK_STONE_REWARD
from models import db


def _day(ts: int) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(ts))


async def my_sect(user_id: int):
    row = await db.fetchone(
        "SELECT s.*, m.role, m.contribution FROM sect_members m "
        "JOIN sects s ON s.id=m.sect_id WHERE m.user_id=?",
        (user_id,))
    return dict(row) if row else None


async def create(user_id: int, name: str, now: int = None) -> dict:
    now = int(time.time()) if now is None else now
    name = name.strip()[:20]
    if not name:
        return {"status": "bad_name"}
    async with db.transaction() as conn:
        cur = await conn.execute("SELECT realm, spirit_stone FROM characters WHERE user_id=?", (user_id,))
        char = await cur.fetchone()
        await cur.close()
        if not char:
            return {"status": "missing"}
        if char["realm"] < CREATE_REALM:
            return {"status": "locked"}
        cur = await conn.execute("SELECT 1 FROM sect_members WHERE user_id=?", (user_id,))
        member = await cur.fetchone()
        await cur.close()
        if member:
            return {"status": "already_member"}
        if char["spirit_stone"] < CREATE_STONE_COST:
            return {"status": "no_stone", "need": CREATE_STONE_COST, "have": char["spirit_stone"]}
        try:
            await conn.execute(
                "INSERT INTO sects(name, level, contribution_pool, leader_user_id, created_at) "
                "VALUES(?,1,0,?,?)",
                (name, user_id, now))
        except Exception:
            return {"status": "name_taken"}
        cur = await conn.execute("SELECT id FROM sects WHERE name=?", (name,))
        sect = await cur.fetchone()
        await cur.close()
        await conn.execute(
            "INSERT INTO sect_members(sect_id, user_id, role, contribution, joined_at) "
            "VALUES(?,?, '宗主', 0, ?)",
            (sect["id"], user_id, now))
        await conn.execute(
            "UPDATE characters SET spirit_stone = spirit_stone - ? WHERE user_id=?",
            (CREATE_STONE_COST, user_id))
        return {"status": "ok", "name": name}


async def join(user_id: int, name: str, now: int = None) -> dict:
    now = int(time.time()) if now is None else now
    async with db.transaction() as conn:
        cur = await conn.execute("SELECT id, name FROM sects WHERE name=?", (name.strip(),))
        sect_row = await cur.fetchone()
        await cur.close()
        if not sect_row:
            return {"status": "not_found"}
        cur = await conn.execute("SELECT 1 FROM sect_members WHERE user_id=?", (user_id,))
        member = await cur.fetchone()
        await cur.close()
        if member:
            return {"status": "already_member"}
        await conn.execute(
            "INSERT INTO sect_members(sect_id, user_id, role, contribution, joined_at) "
            "VALUES(?,?, '弟子', 0, ?)",
            (sect_row["id"], user_id, now))
        return {"status": "ok", "name": sect_row["name"]}


async def leave(user_id: int) -> dict:
    async with db.transaction() as conn:
        cur = await conn.execute("SELECT sect_id, role FROM sect_members WHERE user_id=?", (user_id,))
        member = await cur.fetchone()
        await cur.close()
        if not member:
            return {"status": "not_member"}
        cur = await conn.execute("SELECT COUNT(*) AS c FROM sect_members WHERE sect_id=?", (member["sect_id"],))
        count = await cur.fetchone()
        await cur.close()
        if member["role"] == "宗主" and count["c"] > 1:
            return {"status": "leader_has_members"}
        await conn.execute("DELETE FROM sect_members WHERE user_id=?", (user_id,))
        if count["c"] <= 1:
            await conn.execute("DELETE FROM sects WHERE id=?", (member["sect_id"],))
        return {"status": "ok"}


async def task(user_id: int, now: int = None) -> dict:
    now = int(time.time()) if now is None else now
    day = _day(now)
    async with db.transaction() as conn:
        cur = await conn.execute("SELECT sect_id FROM sect_members WHERE user_id=?", (user_id,))
        member = await cur.fetchone()
        await cur.close()
        if not member:
            return {"status": "not_member"}
        cur = await conn.execute("SELECT done FROM sect_tasks WHERE user_id=? AND day=?", (user_id, day))
        done = await cur.fetchone()
        await cur.close()
        if done and done["done"]:
            return {"status": "done"}
        await conn.execute(
            "INSERT INTO sect_tasks(user_id, day, done) VALUES(?,?,1) "
            "ON CONFLICT(user_id, day) DO UPDATE SET done=1",
            (user_id, day))
        await conn.execute(
            "UPDATE sect_members SET contribution = contribution + ? WHERE user_id=?",
            (TASK_CONTRIBUTION, user_id))
        await conn.execute(
            "UPDATE sects SET contribution_pool = contribution_pool + ? WHERE id=?",
            (TASK_CONTRIBUTION, member["sect_id"]))
        await conn.execute(
            "UPDATE characters SET spirit_stone = spirit_stone + ? WHERE user_id=?",
            (TASK_STONE_REWARD, user_id))
        return {"status": "ok", "contribution": TASK_CONTRIBUTION, "stone": TASK_STONE_REWARD}


async def redeem(user_id: int, item_key: str) -> dict:
    good = SECT_SHOP.get(item_key)
    if not good:
        return {"status": "bad_item"}
    async with db.transaction() as conn:
        cur = await conn.execute(
            "SELECT contribution FROM sect_members WHERE user_id=?", (user_id,))
        member = await cur.fetchone()
        await cur.close()
        if not member:
            return {"status": "not_member"}
        if member["contribution"] < good["contribution"]:
            return {"status": "no_contribution", "need": good["contribution"], "have": member["contribution"]}
        await conn.execute(
            "UPDATE sect_members SET contribution = contribution - ? WHERE user_id=?",
            (good["contribution"], user_id))
        await conn.execute(
            "INSERT INTO inventory(user_id, item_key, qty) VALUES(?,?,?) "
            "ON CONFLICT(user_id, item_key) DO UPDATE SET qty = qty + ?",
            (user_id, item_key, good["qty"], good["qty"]))
        return {"status": "ok", "item": item_name(item_key), "qty": good["qty"],
                "cost": good["contribution"]}


async def members(sect_id: int, limit: int = 10):
    rows = await db.fetchall(
        "SELECT m.user_id, m.role, m.contribution, u.username FROM sect_members m "
        "LEFT JOIN users u ON u.tg_user_id=m.user_id WHERE m.sect_id=? "
        "ORDER BY CASE m.role WHEN '宗主' THEN 0 WHEN '长老' THEN 1 ELSE 2 END, m.contribution DESC "
        "LIMIT ?",
        (sect_id, limit))
    return [dict(row) for row in rows]
