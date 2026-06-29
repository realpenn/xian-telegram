"""道途配置（v2 M2）。"""
from __future__ import annotations

UNLOCK_REALM = 3

RANK_NAMES = ["入门", "小成", "大成", "圆满", "宗师"]

DAO_PATHS = {
    "sword": {
        "name": "剑修",
        "role": "攻伐与 Boss 伤害",
        "bonuses": [
            {"atk_pct": 0.03, "crit_pct": 0.02},
            {"atk_pct": 0.06, "crit_pct": 0.04},
            {"atk_pct": 0.10, "crit_pct": 0.06},
            {"atk_pct": 0.14, "crit_pct": 0.08},
            {"atk_pct": 0.18, "crit_pct": 0.10},
        ],
    },
    "body": {
        "name": "体修",
        "role": "生存与秘境推进",
        "bonuses": [
            {"hp_pct": 0.03, "df_pct": 0.02},
            {"hp_pct": 0.06, "df_pct": 0.04},
            {"hp_pct": 0.10, "df_pct": 0.06},
            {"hp_pct": 0.14, "df_pct": 0.08},
            {"hp_pct": 0.18, "df_pct": 0.10},
        ],
    },
    "alchemy": {
        "name": "丹修",
        "role": "丹药与突破辅助",
        "bonuses": [
            {"mp_pct": 0.03, "alchemy_pct": 0.02},
            {"mp_pct": 0.06, "alchemy_pct": 0.04},
            {"mp_pct": 0.10, "alchemy_pct": 0.06},
            {"mp_pct": 0.14, "alchemy_pct": 0.08},
            {"mp_pct": 0.18, "alchemy_pct": 0.10},
        ],
    },
    "forge": {
        "name": "器修",
        "role": "法宝与强化",
        "bonuses": [
            {"atk_pct": 0.02, "df_pct": 0.02, "forge_pct": 0.02},
            {"atk_pct": 0.04, "df_pct": 0.04, "forge_pct": 0.04},
            {"atk_pct": 0.07, "df_pct": 0.06, "forge_pct": 0.06},
            {"atk_pct": 0.10, "df_pct": 0.08, "forge_pct": 0.08},
            {"atk_pct": 0.13, "df_pct": 0.10, "forge_pct": 0.10},
        ],
    },
    "talisman": {
        "name": "符阵",
        "role": "闭关与洞府效率",
        "bonuses": [
            {"seclusion_pct": 0.03, "spd_pct": 0.02},
            {"seclusion_pct": 0.06, "spd_pct": 0.04},
            {"seclusion_pct": 0.10, "spd_pct": 0.06},
            {"seclusion_pct": 0.14, "spd_pct": 0.08},
            {"seclusion_pct": 0.18, "spd_pct": 0.10},
        ],
    },
}


def path_name(path_key: str) -> str:
    return DAO_PATHS.get(path_key, {}).get("name", path_key)


def rank_name(rank: int) -> str:
    if 0 <= rank < len(RANK_NAMES):
        return RANK_NAMES[rank]
    return RANK_NAMES[-1]


def bonuses_for(path_key: str, rank: int) -> dict:
    path = DAO_PATHS.get(path_key)
    if not path:
        return {}
    idx = max(0, min(int(rank), len(path["bonuses"]) - 1))
    return dict(path["bonuses"][idx])
