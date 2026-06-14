"""历练：选图 → 耗精力 → 即时战斗 → 掉落（灵石/材料/修为，双轨给修为）。"""
from __future__ import annotations

import random

from config.maps import MAPS
from config.realms import realm_label
from services import character
from services.combat import Combatant, simulate


def _roll_drops(m, rng) -> dict:
    drops = {}
    for key, weight, qmin, qmax in m["drops"]:
        if rng.random() < weight / 100.0:
            drops[key] = drops.get(key, 0) + rng.randint(qmin, qmax)
    return drops


def _combatant_from_mob(src) -> Combatant:
    return Combatant(name=src["name"], hp=src["hp"], mp=src["mp"], atk=src["atk"],
                     df=src["df"], spd=src["spd"], crit=src["crit"], skills=list(src["skills"]))


async def explore(user_id: int, map_key: str) -> dict:
    char = await character.get(user_id)
    m = MAPS.get(map_key)
    if not m:
        return {"status": "bad_map"}
    if char.realm < m["realm"]:
        return {"status": "locked", "need": realm_label(m["realm"], 0)}
    cost = m["stamina"]
    if char.stamina < cost:
        return {"status": "no_stamina", "need": cost, "have": char.stamina}
    await character.spend_stamina(user_id, cost)

    rng = random.Random()
    st = await character.stats(char)
    skills = await character.get_skills(user_id)
    player = Combatant(name="道友", hp=st["hp"], mp=st["mp"], atk=st["atk"],
                       df=st["df"], spd=st["spd"], crit=st["crit"], skills=skills or ["普攻"])
    is_boss = rng.random() < m["boss_rate"]
    mob_src = m["boss"] if is_boss else rng.choice(m["mobs"])
    result = simulate(player, _combatant_from_mob(mob_src), seed=rng.randint(1, 10_000_000))
    win = result["winner"] is player

    reward = {"stone": 0, "cult": 0, "drops": {}}
    if win:
        mult = 2 if is_boss else 1
        stone = rng.randint(*m["stone"]) * mult
        cult = m["cult"] * mult
        drops = _roll_drops(m, rng)
        await character.add_stone(user_id, stone)
        await character.set_cultivation(user_id, char.cultivation + cult)
        for k, q in drops.items():
            await character.add_item(user_id, k, q)
        reward = {"stone": stone, "cult": cult, "drops": drops}

    return {"status": "ok", "win": win, "is_boss": is_boss, "mob": mob_src["name"],
            "log": result["log"], "reward": reward, "stamina_left": max(0, char.stamina - cost)}
