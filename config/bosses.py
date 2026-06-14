"""世界 Boss 配置（spec §5.3）。"""
from __future__ import annotations

WORLD_BOSSES = {
    "ancient_dragon": {
        "name": "苍蛟妖皇",
        "realm": 1,
        "hp": 80000,
        "duration": 2 * 3600,
        "stamina": 15,
        "stone_pool": 1800,
        "drops": {"妖丹": 8, "天材地宝": 2, "烈火诀残页": 2},
        "combat": {
            "name": "苍蛟妖皇", "hp": 160000, "mp": 2000, "atk": 650,
            "df": 420, "spd": 150, "crit": 80, "skills": ["普攻", "烈火诀", "金钟罩"],
        },
    }
}

DEFAULT_BOSS = "ancient_dragon"
