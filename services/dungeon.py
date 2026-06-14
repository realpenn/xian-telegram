"""秘境副本：每日限次、逐层即时结算（spec §5.2）。"""
from __future__ import annotations

import random
import time

from config import realms as R
from config.dungeons import DUNGEONS
from config.items import ITEMS, item_name
from services import character, settle
from services.combat import Combatant, simulate
from models import db


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


async def run(user_id: int, dungeon_key: str, now: int = None) -> dict:
    now = int(time.time()) if now is None else now
    d = DUNGEONS.get(dungeon_key)
    if not d:
        return {"status": "bad_dungeon"}
    total_cost = d["stamina"] * d["layers"]
    async with db.transaction() as conn:
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
        if runs and runs["runs"] >= 1:
            return {"status": "daily_done"}
        if stamina < total_cost:
            await conn.execute(
                "UPDATE characters SET stamina=?, stamina_at=? WHERE user_id=?",
                (stamina, stamina_at, user_id))
            return {"status": "no_stamina", "need": total_cost, "have": stamina}
        await conn.execute(
            "UPDATE characters SET stamina=?, stamina_at=? WHERE user_id=?",
            (stamina - total_cost, stamina_at, user_id))
        await conn.execute(
            "INSERT INTO dungeon_runs(user_id, dungeon_key, day, runs) VALUES(?,?,?,1) "
            "ON CONFLICT(user_id, dungeon_key, day) DO UPDATE SET runs = runs + 1",
            (user_id, dungeon_key, _day(now)))
        char = character._from_row(row, stamina - total_cost, stamina_at)

    rng = random.Random(f"{user_id}:{dungeon_key}:{now}")
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

    mult = max(1, cleared)
    stack_drops = {}
    equipment_drops = []
    if cleared:
        welfare = await character.sect_welfare(user_id)
        raw_drops = _roll_drops(d, rng, welfare["drop_pct"])
        for key, qty in raw_drops.items():
            if ITEMS.get(key, {}).get("type") == "equipment":
                for _ in range(qty):
                    await character.create_item_instance(user_id, key)
                    equipment_drops.append(item_name(key))
            else:
                stack_drops[key] = qty
        stone = rng.randint(*d["stone"]) * mult
        cult = d["cult"] * mult
        await character.grant_reward(user_id, stone, cult, stack_drops)
    else:
        stone = cult = 0

    return {"status": "ok", "dungeon": d["name"], "cleared": cleared, "layers": d["layers"],
            "win": cleared == d["layers"], "log": logs,
            "reward": {"stone": stone, "cult": cult, "drops": stack_drops,
                       "equipment": equipment_drops},
            "stamina_left": char.stamina}
