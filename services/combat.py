"""即时自动战斗引擎（spec §7）。确定性带种子模拟，PvE/PvP 共用。

伤害 = max(1, 攻 × 功法系数 × [1 − 防/(防+300)]) × 暴击 × rand(0.9,1.1)
暴击率 = 暴/(暴+200)（上限 50%），暴击 ×1.5；每回合回法力 5%；默认最多 MAX_ROUNDS 回合。
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from config.skills import SKILLS

MAX_ROUNDS = 30
# 「战至分胜负」(max_rounds=None) 的安全兜底：僵局对局（净治疗≥净伤害）本会无限循环，
# 每回合向 log 追加数行 → 内存无界 + 阻塞事件循环。触顶按剩余气血比例判定，与限回合同义。
HARD_ROUND_CAP = 1000
DEF_K = 300
CRIT_K = 200
CRIT_CAP = 0.50
CRIT_MULT = 1.5
MP_REGEN_PCT = 0.05


@dataclass
class Combatant:
    name: str
    hp: int
    mp: int
    atk: int
    df: int
    spd: int
    crit: int
    skills: list            # 战技 key 列表（按优先级）；普攻为隐式兜底
    max_hp: int = 0
    max_mp: int = 0
    lifesteal_pct: float = 0.0
    reflect_pct: float = 0.0
    crit_resist: int = 0
    pierce: int = 0
    initiative: int = 0
    cooldowns: dict = field(default_factory=dict)
    dots: list = field(default_factory=list)   # [[剩余回合, 每回合伤害], ...]
    shield: bool = False
    stunned: bool = False

    def __post_init__(self):
        # 不传 max ⇒ 满血开打（满配模拟/小怪沿用）；显式传 max ⇒ 残血开打仍以满值为上限基准，
        # 使回春术 heal_pct·max_hp 与 _decide 的血量比例判定不被残血污染（#24）。
        self.max_hp = self.max_hp or self.hp
        self.max_mp = self.max_mp or self.mp


def _hit(att, dfn, coef, rng):
    effective_df = max(0, dfn.df - att.pierce)
    raw = att.atk * coef * (1 - effective_df / (effective_df + DEF_K))
    effective_crit = max(0, att.crit - dfn.crit_resist)
    crit_rate = min(CRIT_CAP, effective_crit / (effective_crit + CRIT_K))
    is_crit = rng.random() < crit_rate
    dmg = raw * (CRIT_MULT if is_crit else 1.0) * (0.9 + rng.random() * 0.2)
    return max(1, int(dmg)), is_crit


def _choose_skill(actor):
    for key in actor.skills:
        sk = SKILLS.get(key)
        if not sk:
            continue
        if actor.cooldowns.get(key, 0) > 0:
            continue
        if actor.mp < sk.get("mp", 0):
            continue
        return key
    return "普攻"


def _act(actor, target, rng, log):
    if actor.stunned:
        actor.stunned = False
        log.append(f"❄️ {actor.name} 被定身，难以动弹。")
        return
    key = _choose_skill(actor)
    sk = SKILLS[key]
    actor.mp -= sk.get("mp", 0)
    if sk.get("cd", 0) > 0:
        actor.cooldowns[key] = sk["cd"]
    t = sk["type"]
    if t in ("normal", "burst"):
        dmg, crit = _hit(actor, target, sk["coef"], rng)
        if target.shield:
            target.shield = False
            log.append(f"🛡️ {target.name} 运护盾，挡下「{sk['name']}」！")
        else:
            target.hp -= dmg
            log.append(f"{actor.name} 施「{sk['name']}」{'（暴击）' if crit else ''}，伤 {dmg}。")
            _after_direct_damage(actor, target, dmg, log)
    elif t == "dot":
        dmg, _ = _hit(actor, target, sk["coef"], rng)
        target.dots.append([sk["dur"], dmg])
        log.append(f"{actor.name} 施「{sk['name']}」，灼烧 {sk['dur']} 回合（每回合 {dmg}）。")
    elif t == "heal":
        heal = int(actor.max_hp * sk["heal_pct"])
        actor.hp = min(actor.max_hp, actor.hp + heal)
        log.append(f"{actor.name} 运「{sk['name']}」，回复气血 {heal}。")
    elif t == "shield":
        actor.shield = True
        log.append(f"{actor.name} 立「{sk['name']}」，凝盾御敌。")
    elif t == "stun":
        target.stunned = True
        log.append(f"{actor.name} 祭「{sk['name']}」，定住 {target.name}！")


def _after_direct_damage(actor, target, dmg, log):
    if actor.lifesteal_pct > 0:
        healed = min(actor.max_hp - actor.hp, int(dmg * actor.lifesteal_pct))
        if healed > 0:
            actor.hp += healed
            log.append(f"🩸 {actor.name} 汲取气血 {healed}。")
    if target.reflect_pct > 0 and actor.hp > 0:
        reflected = int(dmg * target.reflect_pct)
        if reflected > 0:
            actor.hp -= reflected
            log.append(f"↩️ {target.name} 反震 {reflected}。")


def _tick_dots(c, log):
    if not c.dots:
        return
    total = 0
    alive = []
    for d in c.dots:
        d[0] -= 1
        total += d[1]
        if d[0] > 0:
            alive.append(d)
    c.dots = alive
    if total:
        c.hp -= total
        log.append(f"🔥 {c.name} 受灼烧，伤 {total}。")


def _tick_cooldowns(c):
    for k in list(c.cooldowns):
        if c.cooldowns[k] > 0:
            c.cooldowns[k] -= 1


def _decide(a, d):
    if a.hp <= 0 and d.hp <= 0:
        return a if a.spd >= d.spd else d
    if d.hp <= 0:
        return a
    if a.hp <= 0:
        return d
    return a if (a.hp / a.max_hp) >= (d.hp / d.max_hp) else d


def round_limit_label(max_rounds: int = MAX_ROUNDS) -> str:
    return f"{max_rounds} 回合"


def _finish_reason(a, d):
    if a.hp <= 0 and d.hp <= 0:
        return "double_down"
    if a.hp <= 0 or d.hp <= 0:
        return "defeat"
    return "round_limit"


def _winner_line(winner, reason, max_rounds: int):
    if reason == "round_limit":
        label = round_limit_label(max_rounds)
        return f"🏆 {winner.name} 胜！（{label}未分胜负，按剩余气血比例判定）"
    return f"🏆 {winner.name} 胜！"


def simulate(a: Combatant, d: Combatant, seed: int = 0, *,
             max_rounds: int | None = MAX_ROUNDS) -> dict:
    rng = random.Random(seed)
    log = [f"⚔️ {a.name} 对阵 {d.name}！"]
    order = (a, d) if (a.spd + a.initiative) >= (d.spd + d.initiative) else (d, a)
    rnd = 0
    max_rounds = None if max_rounds is None else max(1, int(max_rounds))
    cap = HARD_ROUND_CAP if max_rounds is None else max_rounds
    while rnd < cap:
        rnd += 1
        for c in (a, d):
            _tick_dots(c, log)
        if a.hp <= 0 or d.hp <= 0:
            break
        for actor in order:
            target = d if actor is a else a
            if actor.hp <= 0 or target.hp <= 0:
                continue
            _act(actor, target, rng, log)
            if target.hp <= 0:
                break
        for c in (a, d):
            c.mp = min(c.max_mp, c.mp + int(c.max_mp * MP_REGEN_PCT))
            _tick_cooldowns(c)
        if a.hp <= 0 or d.hp <= 0:
            break
    winner = _decide(a, d)
    reason = _finish_reason(a, d)
    log.append(_winner_line(winner, reason, max_rounds or rnd))
    return {"winner": winner, "log": log, "a_hp": max(0, a.hp),
            "d_hp": max(0, d.hp), "rounds": rnd, "reason": reason}
