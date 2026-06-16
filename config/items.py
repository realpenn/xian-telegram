"""物品定义（静态）。type: equipment/material/pill/page/recipe。"""
from __future__ import annotations

ITEMS = {
    "新手剑": {"name": "新手木剑", "type": "equipment", "slot": "weapon",
             "tier": "凡", "bonus": {"atk": 5}},
    "玄铁剑": {"name": "玄铁剑", "type": "equipment", "slot": "weapon",
             "tier": "灵", "bonus": {"atk": 38, "crit": 4}},
    "青木甲": {"name": "青木甲", "type": "equipment", "slot": "armor",
             "tier": "灵", "bonus": {"hp": 160, "df": 28}, "tribulation_shield": 60},
    "聚灵佩": {"name": "聚灵佩", "type": "equipment", "slot": "accessory",
             "tier": "宝", "bonus": {"mp": 80, "spd": 10}, "breakthrough_rate": 0.03},
    "灵草":   {"name": "灵草",     "type": "material", "sell": 4},
    "玄铁矿": {"name": "玄铁矿",   "type": "material", "sell": 8},
    "兽皮":   {"name": "妖兽皮",   "type": "material", "sell": 5},
    "妖丹":   {"name": "妖丹",     "type": "material", "sell": 18},
    "天材地宝": {"name": "天材地宝", "type": "material", "sell": 80},
    "器魂":   {"name": "器魂",     "type": "material", "sell": 6},
    # 困难图独占材料（#20）：留作后续炼丹/炼器/突破扩展，卖价偏低以免成为灵石 faucet。
    "阴风石": {"name": "阴风石",   "type": "material", "sell": 8},
    "幽冥草": {"name": "幽冥草",   "type": "material", "sell": 8},
    "白骨精华": {"name": "白骨精华", "type": "material", "sell": 20},
    "腐泽妖核": {"name": "腐泽妖核", "type": "material", "sell": 20},
    "雷纹玄铁": {"name": "雷纹玄铁", "type": "material", "sell": 50},
    "劫火残晶": {"name": "劫火残晶", "type": "material", "sell": 50},
    "天魔残页": {"name": "天魔残页", "type": "material", "sell": 60},
    "古战魂晶": {"name": "古战魂晶", "type": "material", "sell": 60},
    "疗伤丹": {"name": "疗伤丹",   "type": "pill", "sell": 20},
    "补灵丹": {"name": "补灵丹",   "type": "pill", "sell": 20},
    "虎力丹": {"name": "虎力丹",   "type": "pill", "sell": 35, "use": "buff",
             "buff": {"atk_pct": 0.10}, "duration": 3600},
    "凝神丹": {"name": "凝神丹",   "type": "pill", "sell": 35, "use": "buff",
             "buff": {"seclusion_pct": 0.20}, "duration": 3600},
    "洗髓丹": {"name": "洗髓丹",   "type": "pill", "sell": 120},
    "筑基丹": {"name": "筑基丹",   "type": "pill", "sell": 60},
    "金丹":   {"name": "金丹",     "type": "pill", "sell": 180},
    "元婴丹": {"name": "元婴丹",   "type": "pill", "sell": 500},
    "归元心法残页": {"name": "归元心法残页", "type": "page", "skill": "归元心法", "need": 3},
    "烈火诀残页": {"name": "烈火诀残页", "type": "page", "skill": "烈火诀", "need": 3},
    "回春术残页": {"name": "回春术残页", "type": "page", "skill": "回春术", "need": 3},
    "洗髓丹丹方": {"name": "洗髓丹丹方", "type": "recipe", "recipe": "marrow_pill"},
    "玄铁剑图纸": {"name": "玄铁剑图纸", "type": "recipe", "recipe": "forge_sword"},
    "青木甲图纸": {"name": "青木甲图纸", "type": "recipe", "recipe": "forge_armor"},
    "聚灵佩图纸": {"name": "聚灵佩图纸", "type": "recipe", "recipe": "forge_accessory"},
}


def item_name(key: str) -> str:
    it = ITEMS.get(key)
    return it["name"] if it else key


def weapon_bonus(key: str) -> dict:
    it = ITEMS.get(key)
    if it and it.get("type") == "equipment":
        return dict(it.get("bonus", {}))
    return {}


def is_equipment(key: str) -> bool:
    return ITEMS.get(key, {}).get("type") == "equipment"


def equipment_slot(key: str) -> str:
    return ITEMS.get(key, {}).get("slot", "")


def sell_price(key: str) -> int:
    return int(ITEMS.get(key, {}).get("sell", 0))


def is_usable(key: str) -> bool:
    item = ITEMS.get(key, {})
    return (
        key in {"疗伤丹", "补灵丹", "洗髓丹", "天材地宝"}
        or item.get("use") == "buff"
        or item.get("type") == "recipe"
    )
