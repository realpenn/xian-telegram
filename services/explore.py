"""历练：开始耗精力 → 等待约 10 分钟 → 结算战斗与掉落。"""
from __future__ import annotations

import random
import time

from config.maps import MAPS
from config.realms import realm_label
from models import db
from services import character
from services.combat import Combatant, simulate

EXPLORE_DURATION_SECONDS = 10 * 60
EXPLORE_DURATION_JITTER_SECONDS = 2 * 60


def _roll_drops(m, rng, drop_bonus: float = 0.0) -> dict:
    drops = {}
    for key, weight, qmin, qmax in m["drops"]:
        if rng.random() < min(100.0, weight * (1 + drop_bonus)) / 100.0:
            drops[key] = drops.get(key, 0) + rng.randint(qmin, qmax)
    return drops


def _combatant_from_mob(src) -> Combatant:
    return Combatant(name=src["name"], hp=src["hp"], mp=src["mp"], atk=src["atk"],
                     df=src["df"], spd=src["spd"], crit=src["crit"], skills=list(src["skills"]))


def _uniform(rng, low: float, high: float) -> float:
    if hasattr(rng, "uniform"):
        return rng.uniform(low, high)
    return low + (high - low) * rng.random()


def _run_status(row, now: int) -> dict:
    m = MAPS.get(row["map_key"], {})
    remaining = max(0, row["finish_at"] - now)
    return {
        "status": "ready" if remaining == 0 else "pending",
        "map_key": row["map_key"],
        "map": m.get("name", row["map_key"]),
        "start_at": row["start_at"],
        "finish_at": row["finish_at"],
        "remaining": remaining,
    }


async def active_run(user_id: int, now: int = None):
    now = int(time.time()) if now is None else now
    row = await db.fetchone(
        "SELECT * FROM explore_runs WHERE user_id=? AND status='active'",
        (user_id,))
    return _run_status(row, now) if row else None


async def start(user_id: int, map_key: str, now: int = None, rng=None) -> dict:
    now = int(time.time()) if now is None else now
    m = MAPS.get(map_key)
    if not m:
        return {"status": "bad_map"}
    rng = rng or random.Random()
    async with db.transaction() as conn:
        cur = await conn.execute(
            "SELECT * FROM explore_runs WHERE user_id=? AND status='active'",
            (user_id,))
        active = await cur.fetchone()
        await cur.close()
        if active:
            return _run_status(active, now)

        row = await character._select_character(conn, user_id)
        if not row:
            return {"status": "missing"}
        if row["realm"] < m["realm"]:
            return {"status": "locked", "need": realm_label(m["realm"], 0)}
        welfare = await character._sect_welfare(conn, user_id)
        stamina, stamina_at = character._settled_stamina(row, now, welfare)
        if row["seclusion_at"]:
            await conn.execute(
                "UPDATE characters SET stamina=?, stamina_at=? WHERE user_id=?",
                (stamina, stamina_at, user_id))
            return {"status": "in_seclusion"}
        cost = m["stamina"]
        if stamina < cost:
            await conn.execute(
                "UPDATE characters SET stamina=?, stamina_at=? WHERE user_id=?",
                (stamina, stamina_at, user_id))
            return {"status": "no_stamina", "need": cost, "have": stamina}
        jitter = rng.randint(-EXPLORE_DURATION_JITTER_SECONDS, EXPLORE_DURATION_JITTER_SECONDS)
        finish_at = now + EXPLORE_DURATION_SECONDS + jitter
        seed = rng.randint(1, 10_000_000)
        await conn.execute(
            "UPDATE characters SET stamina=?, stamina_at=? WHERE user_id=?",
            (stamina - cost, stamina_at, user_id))
        await conn.execute(
            "INSERT INTO explore_runs(user_id, map_key, start_at, finish_at, seed, status) "
            "VALUES(?,?,?,?,?,'active')",
            (user_id, map_key, now, finish_at, seed))
        return {
            "status": "started",
            "map_key": map_key,
            "map": m["name"],
            "finish_at": finish_at,
            "seconds": finish_at - now,
            "stamina_left": stamina - cost,
        }


async def collect(user_id: int, now: int = None, rng=None) -> dict:
    now = int(time.time()) if now is None else now
    async with db.transaction() as conn:
        cur = await conn.execute(
            "SELECT * FROM explore_runs WHERE user_id=? AND status='active'",
            (user_id,))
        row = await cur.fetchone()
        await cur.close()
        if not row:
            return {"status": "no_active"}
        if row["finish_at"] > now:
            return _run_status(row, now)
        run = dict(row)
        await conn.execute("DELETE FROM explore_runs WHERE user_id=?", (user_id,))
    return await _resolve(user_id, run["map_key"], run["seed"], now, rng)


async def explore(user_id: int, map_key: str, rng=None, now: int = None) -> dict:
    return await start(user_id, map_key, now, rng)


async def _resolve(user_id: int, map_key: str, seed: int, now: int, rng=None) -> dict:
    m = MAPS.get(map_key)
    if not m:
        return {"status": "bad_map"}
    rng = rng or random.Random(seed)
    char = await character.get_at(user_id, now)
    if not char:
        return {"status": "missing"}
    st = await character.stats(char)
    skills = await character.get_skills(user_id)
    mods = await character.combat_mods(user_id)
    player = Combatant(name="道友", hp=st["hp"], mp=st["mp"], atk=st["atk"],
                       df=st["df"], spd=st["spd"], crit=st["crit"], skills=skills or ["普攻"],
                       **mods)
    is_boss = rng.random() < m["boss_rate"]
    mob_sources = [m["boss"]] if is_boss else [rng.choice(m["mobs"]) for _ in range(rng.randint(1, 3))]
    logs = []
    win = True
    for idx, mob_src in enumerate(mob_sources, 1):
        result = simulate(player, _combatant_from_mob(mob_src), seed=rng.randint(1, 10_000_000))
        logs.append(f"第 {idx} 战：遭遇 {mob_src['name']}")
        shown = result["log"] if len(result["log"]) <= 5 else (result["log"][:4] + ["……", result["log"][-1]])
        logs.extend(shown[1:])
        if result["winner"] is not player:
            win = False
            break
        player.hp = max(1, result["a_hp"])

    reward = {"stone": 0, "cult": 0, "drops": {}}
    if win:
        mult = 2 if is_boss else 1
        stone = rng.randint(*m["stone"]) * mult
        cult = max(1, int(m["cult"] * _uniform(rng, 0.9, 1.1))) * mult
        welfare = await character.sect_welfare(user_id)
        drops = _roll_drops(m, rng, welfare["drop_pct"])
        await character.grant_reward(user_id, stone, cult, drops)
        reward = {"stone": stone, "cult": cult, "drops": drops}

    return {"status": "ok", "map_key": map_key, "map": m["name"],
            "win": win, "is_boss": is_boss,
            "mob": "、".join(src["name"] for src in mob_sources),
            "log": logs, "reward": reward, "stamina_left": char.stamina}
