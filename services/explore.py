"""历练：选图 → 耗精力 → 即时战斗 → 掉落（灵石/材料/修为，双轨给修为）。"""
from __future__ import annotations

import random

from config.maps import MAPS
from config.realms import realm_label
from services import character
from services.combat import Combatant, simulate


def _roll_drops(m, rng, drop_bonus: float = 0.0) -> dict:
    drops = {}
    for key, weight, qmin, qmax in m["drops"]:
        if rng.random() < min(100.0, weight * (1 + drop_bonus)) / 100.0:
            drops[key] = drops.get(key, 0) + rng.randint(qmin, qmax)
    return drops


def _combatant_from_mob(src) -> Combatant:
    return Combatant(name=src["name"], hp=src["hp"], mp=src["mp"], atk=src["atk"],
                     df=src["df"], spd=src["spd"], crit=src["crit"], skills=list(src["skills"]))


async def explore(user_id: int, map_key: str, rng=None) -> dict:
    m = MAPS.get(map_key)
    if not m:
        return {"status": "bad_map"}
    char = await character.get(user_id)
    if not char:
        return {"status": "missing"}
    if char.realm < m["realm"]:
        return {"status": "locked", "need": realm_label(m["realm"], 0)}
    cost = m["stamina"]
    reserved = await character.reserve_stamina_for_action(user_id, cost)
    if reserved["status"] != "ok":
        return reserved
    char = reserved["char"]

    rng = rng or random.Random()
    st = await character.stats(char)
    skills = await character.get_skills(user_id)
    player = Combatant(name="道友", hp=st["hp"], mp=st["mp"], atk=st["atk"],
                       df=st["df"], spd=st["spd"], crit=st["crit"], skills=skills or ["普攻"])
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
        cult = m["cult"] * mult
        welfare = await character.sect_welfare(user_id)
        drops = _roll_drops(m, rng, welfare["drop_pct"])
        await character.grant_reward(user_id, stone, cult, drops)
        reward = {"stone": stone, "cult": cult, "drops": drops}

    return {"status": "ok", "win": win, "is_boss": is_boss,
            "mob": "、".join(src["name"] for src in mob_sources),
            "log": logs, "reward": reward, "stamina_left": reserved["stamina_left"]}
