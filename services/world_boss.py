"""世界 Boss lite：群实例、累计伤害、贡献奖励（spec §5.3）。"""
from __future__ import annotations

import time

from config.bosses import DEFAULT_BOSS, WORLD_BOSSES
from config.items import item_name
from services import character
from services.combat import Combatant, simulate
from models import db


def _day(ts: int) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(ts))


def _boss_combatant(key: str) -> Combatant:
    src = WORLD_BOSSES[key]["combat"]
    return Combatant(name=src["name"], hp=src["hp"], mp=src["mp"], atk=src["atk"],
                     df=src["df"], spd=src["spd"], crit=src["crit"], skills=list(src["skills"]))


async def _active_row(conn, chat_id: int, now: int):
    cur = await conn.execute(
        "SELECT * FROM world_boss WHERE chat_id=? AND status='alive' ORDER BY id DESC LIMIT 1",
        (chat_id,))
    row = await cur.fetchone()
    await cur.close()
    if row and row["expire_at"] <= now:
        await conn.execute("UPDATE world_boss SET status='expired' WHERE id=?", (row["id"],))
        return None
    return row


async def _latest_today(conn, chat_id: int, now: int):
    cur = await conn.execute(
        "SELECT * FROM world_boss WHERE chat_id=? ORDER BY id DESC LIMIT 1",
        (chat_id,))
    row = await cur.fetchone()
    await cur.close()
    if row and _day(row["spawn_at"]) == _day(now):
        return row
    return None


async def ensure_active(chat_id: int, now: int = None):
    now = int(time.time()) if now is None else now
    async with db.transaction() as conn:
        row = await _active_row(conn, chat_id, now)
        if row:
            return row
        latest = await _latest_today(conn, chat_id, now)
        if latest:
            return latest
        cfg = WORLD_BOSSES[DEFAULT_BOSS]
        await conn.execute(
            "INSERT INTO world_boss(chat_id, boss_key, total_hp, remaining_hp, spawn_at, expire_at, status) "
            "VALUES(?,?,?,?,?,?, 'alive')",
            (chat_id, DEFAULT_BOSS, cfg["hp"], cfg["hp"], now, now + cfg["duration"]))
        cur = await conn.execute(
            "SELECT * FROM world_boss WHERE chat_id=? AND status='alive' ORDER BY id DESC LIMIT 1",
            (chat_id,))
        created = await cur.fetchone()
        await cur.close()
        return created


async def status(chat_id: int, now: int = None):
    now = int(time.time()) if now is None else now
    async with db.transaction() as conn:
        boss = await _active_row(conn, chat_id, now)
        if not boss:
            boss = await _latest_today(conn, chat_id, now)
        if not boss:
            return {"status": "none"}
        rows = await _leaderboard(conn, boss["id"])
    return {"status": boss["status"], "boss": dict(boss), "leaderboard": rows}


async def _leaderboard(conn, boss_id: int, limit: int = 5):
    cur = await conn.execute(
        "SELECT d.user_id, d.damage, u.username FROM world_boss_damage d "
        "LEFT JOIN users u ON u.tg_user_id=d.user_id "
        "WHERE d.boss_id=? ORDER BY d.damage DESC LIMIT ?",
        (boss_id, limit))
    rows = await cur.fetchall()
    await cur.close()
    return [dict(row) for row in rows]


async def challenge(chat_id: int, user_id: int, now: int = None) -> dict:
    now = int(time.time()) if now is None else now
    boss = await ensure_active(chat_id, now)
    cfg = WORLD_BOSSES[boss["boss_key"]]
    if boss["status"] == "expired":
        return {"status": "expired"}
    if boss["status"] == "defeated":
        return {"status": "defeated"}
    if boss["remaining_hp"] <= 0:
        return {"status": "defeated"}

    reserve = await character.reserve_stamina_for_action(user_id, cfg["stamina"])
    if reserve["status"] != "ok":
        return reserve
    char = reserve["char"]
    st = await character.stats(char)
    skills = await character.get_skills(user_id)
    player = Combatant(name="道友", hp=st["hp"], mp=st["mp"], atk=st["atk"],
                       df=st["df"], spd=st["spd"], crit=st["crit"], skills=skills or ["普攻"])
    target = _boss_combatant(boss["boss_key"])
    result = simulate(player, target, seed=hash((chat_id, user_id, now)) & 0xFFFFFFFF)
    damage = max(1, target.max_hp - result["d_hp"])

    rewards = []
    defeated = False
    async with db.transaction() as conn:
        current = await _active_row(conn, chat_id, now)
        if not current:
            return {"status": "expired"}
        damage = min(damage, current["remaining_hp"])
        remaining = max(0, current["remaining_hp"] - damage)
        await conn.execute(
            "UPDATE world_boss SET remaining_hp=?, status=? WHERE id=?",
            (remaining, "defeated" if remaining <= 0 else "alive", current["id"]))
        await conn.execute(
            "INSERT INTO world_boss_damage(boss_id, user_id, damage) VALUES(?,?,?) "
            "ON CONFLICT(boss_id, user_id) DO UPDATE SET damage = damage + ?",
            (current["id"], user_id, damage, damage))
        leaderboard = await _leaderboard(conn, current["id"])
        if remaining <= 0:
            defeated = True
            rewards = await _distribute(conn, current["id"], cfg)

    return {"status": "ok", "damage": damage, "remaining_hp": remaining,
            "total_hp": boss["total_hp"], "boss_name": cfg["name"], "defeated": defeated,
            "leaderboard": leaderboard, "rewards": rewards,
            "stamina_left": reserve["stamina_left"]}


async def _distribute(conn, boss_id: int, cfg: dict):
    cur = await conn.execute(
        "SELECT user_id, damage FROM world_boss_damage WHERE boss_id=? ORDER BY damage DESC",
        (boss_id,))
    rows = await cur.fetchall()
    await cur.close()
    total = sum(row["damage"] for row in rows) or 1
    rewards = []
    for idx, row in enumerate(rows):
        stone = max(10, int(cfg["stone_pool"] * row["damage"] / total))
        await conn.execute(
            "UPDATE characters SET spirit_stone = spirit_stone + ? WHERE user_id=?",
            (stone, row["user_id"]))
        drops = {}
        if idx == 0:
            drops = cfg["drops"]
            for key, qty in drops.items():
                await conn.execute(
                    "INSERT INTO inventory(user_id, item_key, qty) VALUES(?,?,?) "
                    "ON CONFLICT(user_id, item_key) DO UPDATE SET qty = qty + ?",
                    (row["user_id"], key, qty, qty))
        rewards.append({"user_id": row["user_id"], "stone": stone, "drops": drops})
    return rewards


def reward_text(rewards: list) -> str:
    if not rewards:
        return ""
    first = rewards[0]
    drops = "、".join(f"{item_name(k)}×{v}" for k, v in first["drops"].items())
    return f"击杀奖励已结算，榜首额外得 {drops}。" if drops else "击杀奖励已结算。"
