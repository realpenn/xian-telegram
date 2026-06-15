"""秘境副本：每日限次、逐层即时结算（spec §5.2）。"""
from __future__ import annotations

import random
import time

from config import realms as R
from config.dungeons import DUNGEONS
from config.items import ITEMS, item_name
from services import character
from services.combat import Combatant, simulate
from models import db

DUNGEON_DURATION_SECONDS = 30 * 60
DUNGEON_DAILY_LIMIT = 3


def _day(now: int) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(now))


def _combatant(src) -> Combatant:
    return Combatant(name=src["name"], hp=src["hp"], mp=src["mp"], atk=src["atk"],
                     df=src["df"], spd=src["spd"], crit=src["crit"], skills=list(src["skills"]))


def _roll_drops(d, rng, drop_bonus: float = 0.0) -> dict:
    drops = {}
    for key, weight, qmin, qmax in d["drops"]:
        if rng.random() < min(100.0, weight * (1 + drop_bonus)) / 100.0:
            drops[key] = drops.get(key, 0) + rng.randint(qmin, qmax)
    return drops


def _uniform(rng, low: float, high: float) -> float:
    if hasattr(rng, "uniform"):
        return rng.uniform(low, high)
    return low + (high - low) * rng.random()


def _run_status(row, now: int) -> dict:
    d = DUNGEONS.get(row["dungeon_key"], {})
    remaining = max(0, row["finish_at"] - now)
    return {
        "status": "ready" if remaining == 0 else "pending",
        "dungeon_key": row["dungeon_key"],
        "dungeon": d.get("name", row["dungeon_key"]),
        "start_at": row["start_at"],
        "finish_at": row["finish_at"],
        "remaining": remaining,
    }


async def active_run(user_id: int, now: int = None):
    now = int(time.time()) if now is None else now
    row = await db.fetchone(
        "SELECT * FROM dungeon_jobs WHERE user_id=? AND status='active'",
        (user_id,))
    return _run_status(row, now) if row else None


async def start(user_id: int, dungeon_key: str, now: int = None, rng=None) -> dict:
    now = int(time.time()) if now is None else now
    d = DUNGEONS.get(dungeon_key)
    if not d:
        return {"status": "bad_dungeon"}
    rng = rng or random.Random(f"{user_id}:{dungeon_key}:{now}")
    total_cost = d["stamina"]
    async with db.transaction() as conn:
        cur = await conn.execute(
            "SELECT * FROM dungeon_jobs WHERE user_id=? AND status='active'",
            (user_id,))
        active = await cur.fetchone()
        await cur.close()
        if active:
            return _run_status(active, now)

        cur = await conn.execute(
            "SELECT 1 FROM explore_runs WHERE user_id=? AND status='active'",
            (user_id,))
        busy = await cur.fetchone()
        await cur.close()
        if busy:
            return {"status": "busy_explore"}

        row = await character._select_character(conn, user_id)
        if not row:
            return {"status": "missing"}
        if row["realm"] < d["realm"]:
            return {"status": "locked", "need": R.realm_label(d["realm"], 0)}
        welfare = await character._sect_welfare(conn, user_id)
        stamina, stamina_at = character._settled_stamina(row, now, welfare)
        if row["seclusion_at"]:
            await conn.execute(
                "UPDATE characters SET stamina=?, stamina_at=? WHERE user_id=?",
                (stamina, stamina_at, user_id))
            return {"status": "in_seclusion"}
        cur = await conn.execute(
            "SELECT runs FROM dungeon_runs WHERE user_id=? AND dungeon_key=? AND day=?",
            (user_id, dungeon_key, _day(now)))
        runs = await cur.fetchone()
        await cur.close()
        if runs and runs["runs"] >= DUNGEON_DAILY_LIMIT:
            return {"status": "daily_done", "limit": DUNGEON_DAILY_LIMIT}
        if stamina < total_cost:
            await conn.execute(
                "UPDATE characters SET stamina=?, stamina_at=? WHERE user_id=?",
                (stamina, stamina_at, user_id))
            return {"status": "no_stamina", "need": total_cost, "have": stamina}
        fee = d.get("entry_stone", 0)
        if fee and row["spirit_stone"] < fee:
            await conn.execute(
                "UPDATE characters SET stamina=?, stamina_at=? WHERE user_id=?",
                (stamina, stamina_at, user_id))
            return {"status": "no_entry_fee", "need": fee, "have": row["spirit_stone"]}
        await conn.execute(
            "UPDATE characters SET stamina=?, stamina_at=?, spirit_stone=spirit_stone-? WHERE user_id=?",
            (stamina - total_cost, stamina_at, fee, user_id))
        await conn.execute(
            "INSERT INTO dungeon_runs(user_id, dungeon_key, day, runs) VALUES(?,?,?,1) "
            "ON CONFLICT(user_id, dungeon_key, day) DO UPDATE SET runs = runs + 1",
            (user_id, dungeon_key, _day(now)))
        finish_at = now + DUNGEON_DURATION_SECONDS
        seed = rng.randint(1, 10_000_000)
        await conn.execute(
            "INSERT INTO dungeon_jobs(user_id, dungeon_key, start_at, finish_at, seed, status) "
            "VALUES(?,?,?,?,?,'active')",
            (user_id, dungeon_key, now, finish_at, seed))
        return {
            "status": "started",
            "dungeon_key": dungeon_key,
            "dungeon": d["name"],
            "finish_at": finish_at,
            "seconds": DUNGEON_DURATION_SECONDS,
            "stamina_left": stamina - total_cost,
            "entry_fee": fee,
        }


async def collect(user_id: int, now: int = None, rng=None) -> dict:
    now = int(time.time()) if now is None else now
    async with db.transaction() as conn:
        cur = await conn.execute(
            "SELECT * FROM dungeon_jobs WHERE user_id=? AND status='active'",
            (user_id,))
        row = await cur.fetchone()
        await cur.close()
        if not row:
            return {"status": "no_active"}
        if row["finish_at"] > now:
            return _run_status(row, now)
        # 在同一事务内结算并删除，避免"已删但奖励未发"的崩溃窗口。
        result = await _resolve(user_id, row["dungeon_key"], row["seed"], now, rng, conn=conn)
        await conn.execute("DELETE FROM dungeon_jobs WHERE user_id=?", (user_id,))
        return result


async def run(user_id: int, dungeon_key: str, now: int = None) -> dict:
    return await start(user_id, dungeon_key, now)


async def _resolve(user_id: int, dungeon_key: str, seed: int, now: int, rng=None, conn=None) -> dict:
    d = DUNGEONS.get(dungeon_key)
    if not d:
        return {"status": "bad_dungeon"}
    rng = rng or random.Random(seed)
    if conn is not None:
        # 已在写事务内：只读取角色（不触发 get_at 的精力落库写，避免重入写锁死锁）。
        row = await character._select_character(conn, user_id)
        char = character._from_row(row) if row else None
    else:
        char = await character.get_at(user_id, now)
    if not char:
        return {"status": "missing"}
    st = await character.stats(char)
    skills = await character.get_skills(user_id)
    mods = await character.combat_mods(user_id)
    player = Combatant(name="道友", hp=st["hp"], mp=st["mp"], atk=st["atk"],
                       df=st["df"], spd=st["spd"], crit=st["crit"], skills=skills or ["普攻"],
                       **mods)
    logs = []
    cleared = 0
    for layer in range(1, d["layers"] + 1):
        mob_src = d["boss"] if layer == d["layers"] else rng.choice(d["mobs"])
        result = simulate(player, _combatant(mob_src), seed=rng.randint(1, 10_000_000))
        logs.append(f"第 {layer} 层：{mob_src['name']}，{'胜' if result['winner'] is player else '败'}")
        if result["winner"] is not player:
            break
        cleared += 1
        player.hp = max(1, result["a_hp"])

    stack_drops = {}
    equipment_drops = []
    if cleared:
        reward_factor = _uniform(rng, 4.0, 6.0) * (cleared / d["layers"])
        welfare = await character.sect_welfare(user_id)
        raw_drops = _roll_drops(d, rng, welfare["drop_pct"])
        for key, qty in raw_drops.items():
            if ITEMS.get(key, {}).get("type") == "equipment":
                for _ in range(qty):
                    if conn is not None:
                        await character._create_item_instance_conn(conn, user_id, key)
                    else:
                        await character.create_item_instance(user_id, key)
                    equipment_drops.append(item_name(key))
            else:
                stack_drops[key] = qty
        stone = int(rng.randint(*d["stone"]) * reward_factor)
        cult = int(d["cult"] * reward_factor)
        if conn is not None:
            await character._grant_reward_conn(conn, user_id, stone, cult, stack_drops)
        else:
            await character.grant_reward(user_id, stone, cult, stack_drops)
    else:
        stone = cult = 0

    return {"status": "ok", "dungeon_key": dungeon_key, "dungeon": d["name"],
            "cleared": cleared, "layers": d["layers"],
            "win": cleared == d["layers"], "log": logs,
            "reward": {"stone": stone, "cult": cult, "drops": stack_drops,
                       "equipment": equipment_drops},
            "stamina_left": char.stamina}
