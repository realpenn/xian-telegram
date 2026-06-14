"""切磋 / 天梯（spec §10）。"""
from __future__ import annotations

import random
import time

from services import character
from services.combat import Combatant, simulate
from models import db

K_FACTOR = 32
DAILY_LIMIT = 10


def _day(ts: int) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(ts))


def _expected(ra: int, rb: int) -> float:
    return 1 / (1 + 10 ** ((rb - ra) / 400))


def _delta(ra: int, rb: int, score: float) -> int:
    return int(round(K_FACTOR * (score - _expected(ra, rb))))


async def ensure_rating(conn, user_id: int):
    await conn.execute(
        "INSERT OR IGNORE INTO pvp_ratings(user_id, rating, wins, losses, daily_count, daily_reset_at) "
        "VALUES(?,1000,0,0,0,0)",
        (user_id,))


async def _rating(conn, user_id: int):
    await ensure_rating(conn, user_id)
    cur = await conn.execute("SELECT * FROM pvp_ratings WHERE user_id=?", (user_id,))
    row = await cur.fetchone()
    await cur.close()
    return row


async def random_opponent(user_id: int):
    me = await character.get(user_id)
    if not me:
        return None
    my_rating = await db.fetchone(
        "SELECT rating FROM pvp_ratings WHERE user_id=?", (user_id,))
    rating = my_rating["rating"] if my_rating else 1000
    rows = await db.fetchall(
        "SELECT c.user_id, c.realm, c.seclusion_at, COALESCE(p.rating, 1000) AS rating "
        "FROM characters c LEFT JOIN pvp_ratings p ON p.user_id=c.user_id "
        "WHERE c.user_id<>?",
        (user_id,))
    eligible = [
        row for row in rows
        if not row["seclusion_at"] and abs(row["realm"] - me.realm) <= 1
    ]
    close = [row for row in eligible if abs(row["rating"] - rating) <= 200]
    if close:
        eligible = close
    if not eligible:
        eligible = [row for row in rows if not row["seclusion_at"]]
    return random.choice(eligible)["user_id"] if eligible else None


async def opponent_from_arg(arg: str):
    arg = (arg or "").strip()
    if not arg:
        return {"status": "empty"}
    if arg.startswith("@"):
        username = arg[1:].strip().lower()
        if not username:
            return {"status": "not_found"}
        row = await db.fetchone(
            "SELECT tg_user_id, username FROM users WHERE lower(username)=?",
            (username,))
        if not row:
            return {"status": "not_found"}
        return {"status": "ok", "user_id": row["tg_user_id"],
                "name": "@" + (row["username"] or str(row["tg_user_id"]))}
    if arg.startswith("#") and arg[1:].isdigit():
        rank = int(arg[1:])
        if rank <= 0:
            return {"status": "not_found"}
        rows = await top(rank)
        if len(rows) < rank:
            return {"status": "not_found"}
        row = rows[rank - 1]
        return {"status": "ok", "user_id": row["user_id"],
                "name": row["username"] or f"榜第{rank}"}
    if arg.isdigit():
        row = await db.fetchone(
            "SELECT tg_user_id, username FROM users WHERE tg_user_id=?",
            (int(arg),))
        if row:
            return {"status": "ok", "user_id": row["tg_user_id"],
                    "name": row["username"] or row["tg_user_id"]}
    return {"status": "not_found"}


async def _combatant(user_id: int, name: str) -> Combatant:
    char = await character.get(user_id)
    st = await character.stats(char)
    skills = await character.get_skills(user_id)
    return Combatant(name=name, hp=st["hp"], mp=st["mp"], atk=st["atk"],
                     df=st["df"], spd=st["spd"], crit=st["crit"], skills=skills or ["普攻"])


async def duel(attacker_id: int, defender_id: int = None, now: int = None) -> dict:
    now = int(time.time()) if now is None else now
    if defender_id is None:
        defender_id = await random_opponent(attacker_id)
    if not defender_id:
        return {"status": "no_opponent"}
    if attacker_id == defender_id:
        return {"status": "self"}

    attacker = await character.get(attacker_id)
    defender = await character.get(defender_id)
    if not attacker or not defender:
        return {"status": "missing"}
    if attacker.seclusion_at:
        return {"status": "in_seclusion"}
    if defender.seclusion_at:
        return {"status": "opponent_busy"}
    if abs(attacker.realm - defender.realm) > 1:
        return {"status": "realm_gap"}

    day = _day(now)
    async with db.transaction() as conn:
        ar = await _rating(conn, attacker_id)
        dr = await _rating(conn, defender_id)
        daily_count = ar["daily_count"] if ar["daily_reset_at"] == day else 0
        if daily_count >= DAILY_LIMIT:
            return {"status": "daily_limit", "limit": DAILY_LIMIT}
        await conn.execute(
            "UPDATE pvp_ratings SET daily_count=?, daily_reset_at=? WHERE user_id=?",
            (daily_count + 1, day, attacker_id))

    a = await _combatant(attacker_id, "道友")
    d = await _combatant(defender_id, "对手")
    result = simulate(a, d, seed=hash((attacker_id, defender_id, now)) & 0xFFFFFFFF)
    attacker_win = result["winner"] is a

    async with db.transaction() as conn:
        ar = await _rating(conn, attacker_id)
        dr = await _rating(conn, defender_id)
        score = 1.0 if attacker_win else 0.0
        change = _delta(ar["rating"], dr["rating"], score)
        defender_change = _delta(dr["rating"], ar["rating"], 1.0 - score)
        await conn.execute(
            "UPDATE pvp_ratings SET rating=?, wins=wins+?, losses=losses+? WHERE user_id=?",
            (max(0, ar["rating"] + change), 1 if attacker_win else 0,
             0 if attacker_win else 1, attacker_id))
        await conn.execute(
            "UPDATE pvp_ratings SET rating=?, wins=wins+?, losses=losses+? WHERE user_id=?",
            (max(0, dr["rating"] + defender_change), 0 if attacker_win else 1,
             1 if attacker_win else 0, defender_id))
        await conn.execute(
            "UPDATE characters SET spirit_stone = spirit_stone + ? WHERE user_id=?",
            (20 if attacker_win else 5, attacker_id))

    return {"status": "ok", "win": attacker_win, "rating_delta": change,
            "defender_id": defender_id, "log": result["log"],
            "rounds": result["rounds"]}


async def top(limit: int = 10):
    rows = await db.fetchall(
        "SELECT p.user_id, p.rating, p.wins, p.losses, u.username "
        "FROM pvp_ratings p LEFT JOIN users u ON u.tg_user_id=p.user_id "
        "ORDER BY p.rating DESC, p.wins DESC LIMIT ?",
        (limit,))
    return [dict(row) for row in rows]


def tier(rating: int) -> str:
    if rating >= 1600:
        return "地仙"
    if rating >= 1400:
        return "仙品"
    if rating >= 1200:
        return "宝品"
    if rating >= 1000:
        return "灵品"
    return "凡品"
