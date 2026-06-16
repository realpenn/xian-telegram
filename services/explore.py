"""历练：开始耗精力 → 等待约 10 分钟 → 结算战斗与掉落。"""
from __future__ import annotations

import random
import time

from config.maps import MAPS
from config.realms import realm_label
from models import db
from services import character
from services.combat import Combatant, simulate

# 历练时长与遭遇密度按难度绑定（#20）：开局即定遭遇计划与时长，结算复用。
# enc=(最少, 最多) 场遭遇；minutes=(下限, 上限) 时长区间。
DIFFICULTY_PLAN = {
    "易": {"enc": (1, 1), "minutes": (8, 10)},
    "中": {"enc": (1, 2), "minutes": (10, 13)},
    "难": {"enc": (2, 3), "minutes": (13, 16)},
}


def _plan_minutes(m, is_boss: bool, n_enc: int) -> float:
    plan = DIFFICULTY_PLAN.get(m.get("difficulty", "易"), DIFFICULTY_PLAN["易"])
    lo, hi = plan["minutes"]
    elo, ehi = plan["enc"]
    if is_boss:
        return hi                       # 妖王战耗时最长
    if ehi == elo:
        return (lo + hi) / 2
    return lo + (hi - lo) * (n_enc - elo) / (ehi - elo)


def _roll_plan(m, rng):
    """开局决定本次遭遇计划：是否妖王 + 遭遇场数 + 时长。"""
    plan = DIFFICULTY_PLAN.get(m.get("difficulty", "易"), DIFFICULTY_PLAN["易"])
    is_boss = rng.random() < m["boss_rate"]
    n_enc = 1 if is_boss else rng.randint(*plan["enc"])
    seconds = int(_plan_minutes(m, is_boss, n_enc) * 60)
    return is_boss, n_enc, seconds


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

        cur = await conn.execute(
            "SELECT 1 FROM dungeon_jobs WHERE user_id=? AND status='active'",
            (user_id,))
        busy = await cur.fetchone()
        await cur.close()
        if busy:
            return {"status": "busy_dungeon"}

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
        # 开局即定遭遇计划与时长，并落库；结算阶段复用，使时长与战斗数量不脱钩（#20）。
        is_boss, n_enc, seconds = _roll_plan(m, rng)
        finish_at = now + seconds
        seed = rng.randint(1, 10_000_000)
        await conn.execute(
            "UPDATE characters SET stamina=?, stamina_at=? WHERE user_id=?",
            (stamina - cost, stamina_at, user_id))
        await conn.execute(
            "INSERT INTO explore_runs(user_id, map_key, start_at, finish_at, seed, status, "
            "encounters, is_boss) VALUES(?,?,?,?,?,'active',?,?)",
            (user_id, map_key, now, finish_at, seed, n_enc, 1 if is_boss else 0))
        return {
            "status": "started",
            "map_key": map_key,
            "map": m["name"],
            "difficulty": m.get("difficulty", "易"),
            "finish_at": finish_at,
            "seconds": finish_at - now,
            "encounters": n_enc,
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
        # 在同一事务内结算并删除，避免"已删但奖励未发"的崩溃窗口。
        # 旧库在途历练的 encounters/is_boss 为 NULL，传 None 触发 _resolve 的兼容分支。
        stored_boss = row["is_boss"]
        result = await _resolve(
            user_id, row["map_key"], row["seed"], now, rng, conn=conn,
            n_enc=row["encounters"],
            is_boss=None if stored_boss is None else bool(stored_boss))
        await conn.execute("DELETE FROM explore_runs WHERE user_id=?", (user_id,))
        return result


async def explore(user_id: int, map_key: str, rng=None, now: int = None) -> dict:
    return await start(user_id, map_key, now, rng)


async def _resolve(user_id: int, map_key: str, seed: int, now: int, rng=None, conn=None,
                   n_enc: int = None, is_boss: bool = None) -> dict:
    m = MAPS.get(map_key)
    if not m:
        return {"status": "bad_map"}
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
    if is_boss is None:
        # 兼容无存储计划的旧 run：即时 roll 一份计划。
        is_boss = rng.random() < m["boss_rate"]
        n_enc = 1 if is_boss else rng.randint(1, 3)
    mob_sources = ([m["boss"]] if is_boss
                   else [rng.choice(m["mobs"]) for _ in range(max(1, n_enc or 1))])
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
        if conn is not None:
            await character._grant_reward_conn(conn, user_id, stone, cult, drops)
        else:
            await character.grant_reward(user_id, stone, cult, drops)
        reward = {"stone": stone, "cult": cult, "drops": drops}

    return {"status": "ok", "map_key": map_key, "map": m["name"],
            "win": win, "is_boss": is_boss,
            "mob": "、".join(src["name"] for src in mob_sources),
            "log": logs, "reward": reward, "stamina_left": char.stamina}
