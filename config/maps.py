"""历练地图：妖兽池、妖王、掉落表、修为奖励（静态，初版可调）。

掉落格式：(item_key, weight_percent, qty_min, qty_max)。
"""
from __future__ import annotations


def _mob(name, hp, atk, df, spd, crit, skills=("普攻",)):
    return {"name": name, "hp": hp, "mp": 50, "atk": atk, "df": df,
            "spd": spd, "crit": crit, "skills": list(skills)}


MAPS = {
    "后山": {
        "name": "青牛后山", "realm": 0, "stamina": 10, "cult": 20,
        "mobs": [_mob("灵狐", 180, 22, 12, 16, 4), _mob("青蛇", 220, 26, 14, 12, 5)],
        "boss": _mob("千年青牛", 600, 40, 26, 18, 8, ("普攻", "快剑斩")),
        "boss_rate": 0.10, "stone": (15, 35),
        "drops": [("灵草", 60, 1, 2), ("兽皮", 30, 1, 1), ("妖丹", 8, 1, 1),
                  ("筑基丹", 2, 1, 1)],
    },
    "妖兽森林": {
        "name": "妖兽森林", "realm": 1, "stamina": 10, "cult": 120,
        "mobs": [_mob("赤焰狼", 900, 120, 70, 45, 14), _mob("铁甲犀", 1300, 100, 95, 30, 10)],
        "boss": _mob("噬魂狼王", 2600, 190, 120, 60, 22, ("普攻", "快剑斩")),
        "boss_rate": 0.10, "stone": (40, 90),
        "drops": [("玄铁矿", 55, 1, 2), ("兽皮", 30, 1, 2), ("妖丹", 12, 1, 1),
                  ("金丹", 3, 1, 1)],
    },
    "万妖岭": {
        "name": "万妖岭", "realm": 2, "stamina": 15, "cult": 800,
        "mobs": [_mob("妖象", 4200, 360, 240, 110, 40), _mob("毒蛟", 3600, 420, 200, 130, 48)],
        "boss": _mob("万妖之主·蛟", 9000, 600, 360, 150, 70, ("普攻", "烈火诀")),
        "boss_rate": 0.08, "stone": (120, 240),
        "drops": [("玄铁矿", 50, 2, 4), ("妖丹", 25, 1, 2), ("元婴丹", 3, 1, 1)],
    },
    "上古战场": {
        "name": "上古战场", "realm": 3, "stamina": 15, "cult": 5000,
        "mobs": [_mob("残魂兵", 13000, 1000, 720, 300, 110), _mob("魔焰将", 11000, 1200, 650, 340, 130)],
        "boss": _mob("残魂魔将", 26000, 1700, 1000, 380, 150, ("普攻", "烈火诀", "快剑斩")),
        "boss_rate": 0.08, "stone": (300, 600),
        "drops": [("妖丹", 40, 2, 3), ("元婴丹", 3, 1, 1)],
    },
}


def maps_for_realm(realm: int):
    """返回当前境界可进入的地图 [(key, data), ...]。"""
    return [(k, v) for k, v in MAPS.items() if v["realm"] <= realm]
