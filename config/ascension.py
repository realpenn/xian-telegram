"""飞升点与账号级被动（v2 M3）。"""
from __future__ import annotations

PASSIVE_CAP = 5
TRIAL_DAOHANG_COST = 500
TRIAL_POINT_REWARD = 1
POINTS_PER_PASSIVE_LEVEL = 1
PASSIVES = {
    "hp_pct": "气血",
    "atk_pct": "攻伐",
    "df_pct": "护体",
    "seclusion_pct": "闭关",
}


def passive_name(key: str) -> str:
    return PASSIVES.get(key, key)
