"""功法定义（静态）。type: normal/burst/dot/heal/shield/stun/mind。"""
from __future__ import annotations

SKILLS = {
    "吐纳诀": {"name": "吐纳诀", "type": "mind", "bonus": {"mp_pct": 0.08, "df_pct": 0.03}},
    "归元心法": {"name": "归元心法", "type": "mind", "bonus": {"hp_pct": 0.06, "atk_pct": 0.03}},
    "普攻":   {"name": "普通攻击", "type": "normal", "coef": 1.0, "mp": 0,  "cd": 0},
    "快剑斩": {"name": "快剑斩",   "type": "burst",  "coef": 1.8, "mp": 20, "cd": 2},
    "烈火诀": {"name": "烈火诀",   "type": "dot",    "coef": 0.6, "dur": 3, "mp": 30, "cd": 4},
    "回春术": {"name": "回春术",   "type": "heal",   "heal_pct": 0.15, "mp": 30, "cd": 3},
    "金钟罩": {"name": "金钟罩",   "type": "shield", "mp": 20, "cd": 3},
    "定身符": {"name": "定身符",   "type": "stun",   "mp": 25, "cd": 3},
}

# 新注册角色初始战技。
STARTER_SKILL = "快剑斩"
STARTER_MIND = "吐纳诀"
MIND_SLOT = -1
COMBAT_SLOTS = range(3)


def skill_name(key: str) -> str:
    sk = SKILLS.get(key)
    return sk["name"] if sk else key


def is_mind_skill(key: str) -> bool:
    return SKILLS.get(key, {}).get("type") == "mind"


def skill_bonus(key: str) -> dict:
    return dict(SKILLS.get(key, {}).get("bonus", {}))
