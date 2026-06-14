"""秘境配置（spec §5.2）。"""
from __future__ import annotations


def _mob(name, hp, atk, df, spd, crit, skills=("普攻",)):
    return {"name": name, "hp": hp, "mp": 80, "atk": atk, "df": df,
            "spd": spd, "crit": crit, "skills": list(skills)}


DUNGEONS = {
    "qingyun": {
        "name": "青云秘境", "realm": 2, "layers": 5, "stamina": 20,
        "stone": (180, 300), "cult": 1200,
        "mobs": [
            _mob("秘境石傀", 4200, 360, 260, 100, 35),
            _mob("青云剑影", 3600, 430, 190, 150, 55, ("普攻", "快剑斩")),
        ],
        "boss": _mob("青云守境人", 9500, 680, 420, 180, 80, ("普攻", "快剑斩", "金钟罩")),
        "drops": [
            ("天材地宝", 45, 1, 1),
            ("归元心法残页", 25, 1, 1),
            ("烈火诀残页", 30, 1, 1),
            ("回春术残页", 25, 1, 1),
            ("洗髓丹丹方", 12, 1, 1),
            ("玄铁剑图纸", 20, 1, 1),
            ("青木甲图纸", 16, 1, 1),
            ("聚灵佩图纸", 12, 1, 1),
            ("聚灵佩", 6, 1, 1),
        ],
    }
}
