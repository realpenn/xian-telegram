"""平衡 / 经济模拟器（issues #13-#16 的共同地基）。

纯函数,基于 ``services.combat.simulate``,不碰 DB。玩家属性按
``services.character.stats`` 的同样顺序构造(装备平加 → 心法乘算)。
固定 seed=0..N-1,胜率是确定值,可直接做回归断言。

直接运行打印报告::

    python -m tools.balance_sim
"""
from __future__ import annotations

import random

from config import realms as R
from config.bosses import WORLD_BOSSES
from config.dungeons import DUNGEONS
from config.items import ITEMS
from config.maps import MAPS
from config.skills import SKILLS
from services.combat import Combatant, simulate

# 标准调参档:"满配无词条"——某境界玩家*应当*能通关内容的地板线。
GEARED = {"skills": ["快剑斩", "烈火诀", "回春术", "普攻"],
          "mind": "吐纳诀", "equip": ["玄铁剑", "青木甲", "聚灵佩"]}
STARTER = {"skills": ["快剑斩", "普攻"], "mind": "吐纳诀", "equip": ["新手剑"]}

# 每张图/秘境对应的"解锁境界"。
CONTENT_REALM = {"后山": 0, "妖兽森林": 1, "万妖岭": 2, "上古战场": 3}


def build_player_stats(realm: int, stage: int, profile=GEARED) -> dict:
    base = R.base_stats(realm, stage)
    for key in profile.get("equip", []):
        for k, v in ITEMS.get(key, {}).get("bonus", {}).items():
            base[k] = base.get(k, 0) + v
    mind = SKILLS.get(profile.get("mind"))
    if mind:
        for k, v in mind.get("bonus", {}).items():
            if k.endswith("_pct"):
                sk = k[:-4]
                base[sk] = int(base.get(sk, 0) * (1 + v))
            else:
                base[k] = base.get(k, 0) + v
    return base


def player(realm: int, stage: int, profile=GEARED) -> Combatant:
    st = build_player_stats(realm, stage, profile)
    return Combatant(name="道友", hp=st["hp"], mp=st["mp"], atk=st["atk"],
                     df=st["df"], spd=st["spd"], crit=st["crit"],
                     skills=list(profile["skills"]))


def _mob(src: dict) -> Combatant:
    return Combatant(name=src["name"], hp=src["hp"], mp=src.get("mp", 50),
                     atk=src["atk"], df=src["df"], spd=src["spd"],
                     crit=src["crit"], skills=list(src["skills"]))


def winrate(realm: int, stage: int, mob_src: dict, profile=GEARED, n: int = 300) -> float:
    wins = 0
    for s in range(n):
        p = player(realm, stage, profile)
        if simulate(p, _mob(mob_src), seed=s)["winner"] is p:
            wins += 1
    return wins / n


def map_winrates(realm: int, stage: int, map_key: str, profile=GEARED, n: int = 300):
    """返回 (平均小怪胜率, Boss 胜率)。"""
    m = MAPS[map_key]
    mob = sum(winrate(realm, stage, mb, profile, n) for mb in m["mobs"]) / len(m["mobs"])
    boss = winrate(realm, stage, m["boss"], profile, n)
    return mob, boss


def map_run_winrate(realm: int, stage: int, map_key: str,
                    profile=GEARED, n: int = 300) -> float:
    """复刻 explore._resolve 的小怪连战(1-3 个,血量结转)运行胜率。"""
    m = MAPS[map_key]
    wins = 0
    for s in range(n):
        rng = random.Random(s)
        p = player(realm, stage, profile)
        ok = True
        for _ in range(rng.randint(1, 3)):
            res = simulate(p, _mob(rng.choice(m["mobs"])), seed=rng.randint(1, 10_000_000))
            if res["winner"] is not p:
                ok = False
                break
            p.hp = max(1, res["a_hp"])
        wins += ok
    return wins / n


def dungeon_clear_fraction(realm: int, stage: int, dungeon_key: str,
                           profile=GEARED, n: int = 200) -> float:
    """平均通关层数比例,复刻 services.dungeon 的逐层血量结转。"""
    d = DUNGEONS[dungeon_key]
    total = 0.0
    for s in range(n):
        rng = random.Random(s)
        p = player(realm, stage, profile)
        cleared = 0
        for layer in range(1, d["layers"] + 1):
            mob_src = d["boss"] if layer == d["layers"] else rng.choice(d["mobs"])
            res = simulate(p, _mob(mob_src), seed=rng.randint(1, 10_000_000))
            if res["winner"] is not p:
                break
            cleared += 1
            p.hp = max(1, res["a_hp"])
        total += cleared / d["layers"]
    return total / n


def boss_damage_per_challenge(realm: int, stage: int, boss_key: str,
                              profile=GEARED, n: int = 200) -> float:
    """单次挑战对世界 Boss 战斗假人造成的平均伤害。"""
    cfg = WORLD_BOSSES[boss_key]
    combat = cfg["combat"]
    total = 0
    for s in range(n):
        p = player(realm, stage, profile)
        target = _mob(combat)
        res = simulate(p, target, seed=s)
        total += max(1, target.max_hp - res["d_hp"])
    return total / n


def world_boss_kill_challenges(boss_key: str, realm: int, stage: int, n: int = 200) -> float:
    """该档玩家击杀世界 Boss 所需的总挑战次数 = total_hp / 单次伤害。"""
    cfg = WORLD_BOSSES[boss_key]
    return cfg["total_hp"] / boss_damage_per_challenge(realm, stage, boss_key, n=n)


# ---- 经济:套利 ----

def map_stone_per_stamina(map_key: str) -> float:
    m = MAPS[map_key]
    return (sum(m["stone"]) / 2) / m["stamina"]


def dungeon_stone_per_stamina(dungeon_key: str, reward_factor: float = 5.0) -> float:
    """满层结算近似:reward_factor≈4-6(取5),见 services.dungeon._resolve。"""
    d = DUNGEONS[dungeon_key]
    gross = (sum(d["stone"]) / 2) * reward_factor
    return gross / d["stamina"]


def best_content_stone_per_stamina(realm: int) -> float:
    """该境界可进入的最佳灵石产出(图与秘境取较高者)。"""
    vals = [map_stone_per_stamina(k) for k, m in MAPS.items() if m["realm"] <= realm]
    vals += [dungeon_stone_per_stamina(k) for k, d in DUNGEONS.items() if d["realm"] <= realm]
    return max(vals) if vals else 0.0


# ---- 报告 ----

def _bar(x: float) -> str:
    return "█" * int(round(x * 20))


def report() -> None:
    print("=" * 78)
    print("玩家属性(满配无词条)  hp/atk/df/spd/crit")
    for r in range(4):
        for stage in (0, R.num_stages(r) - 1):
            st = build_player_stats(r, stage, GEARED)
            print(f"  {R.realm_label(r, stage):<12} "
                  f"hp{st['hp']:>6} atk{st['atk']:>5} df{st['df']:>5} "
                  f"spd{st['spd']:>4} crit{st['crit']:>4}")
    print("=" * 78)
    print("地图胜率(满配):  小怪=连战(1-3怪)运行胜率, Boss=单场   [入门可刷, Boss 作后期门槛]")
    for mkey, m in MAPS.items():
        r = m["realm"]
        last = R.num_stages(r) - 1
        e_run = map_run_winrate(r, 0, mkey)
        _, e_boss = map_winrates(r, 0, mkey)
        f_run = map_run_winrate(r, last, mkey)
        _, f_boss = map_winrates(r, last, mkey)
        print(f"  {m['name']:<10}(r{r}) 入门 连战{e_run*100:5.1f}% Boss{e_boss*100:5.1f}%"
              f"   圆满 连战{f_run*100:5.1f}% Boss{f_boss*100:5.1f}%")
    print("-" * 78)
    print("秘境平均通关层比例(满配):  解锁初期 → 圆满   [目标 入门至少过半,部分档位可接近通关]")
    for dkey, d in DUNGEONS.items():
        r = d["realm"]
        last = R.num_stages(r) - 1
        e = dungeon_clear_fraction(r, 0, dkey)
        f = dungeon_clear_fraction(r, last, dkey)
        print(f"  {d['name']:<10}(r{r}) 入门 {e*100:5.1f}% {_bar(e):<20} 圆满 {f*100:5.1f}%")
    print("=" * 78)
    print("世界 Boss 单次伤害 & 击杀所需挑战次数(满配)")
    for bkey, cfg in WORLD_BOSSES.items():
        r = cfg["realm"]
        typ = min(2, R.num_stages(r) - 1)   # 典型参与者=后期
        dmg = boss_damage_per_challenge(r, typ, bkey)
        total = cfg["total_hp"]
        print(f"  {cfg['name']:<10} 档位r{r} total_hp{total:>7} 假人hp{cfg['combat']['hp']:>8} "
              f"  后期伤/次≈{dmg:8.0f}  击杀≈{total/dmg:5.1f}次(目标20-80)")
    print("=" * 78)
    print("经济套利:  首买精力成本/精力  vs  最佳内容产出/精力   (成本>产出 即套利已堵)")
    from services import shop
    for r in range(4):
        best = best_content_stone_per_stamina(r)
        cost_per = shop.first_buy_cost_per_stamina(r) if hasattr(
            shop, "first_buy_cost_per_stamina") else (
            shop.STAMINA_STONE_COST / shop.STAMINA_STONE_GAIN)
        flag = "  ✅堵住" if cost_per > best else "  ⚠️套利"
        print(f"  {R.REALM_NAMES[r]:<6} 最佳内容 {best:6.1f} 灵石/精力   "
              f"首买成本 {cost_per:6.1f} 灵石/精力{flag}")


if __name__ == "__main__":
    report()
