"""物品定义（静态）。type: equipment/material/pill/page/recipe。"""
from __future__ import annotations

ITEMS = {
    "新手剑": {"name": "新手木剑", "type": "equipment", "slot": "weapon",
             "tier": "凡", "bonus": {"atk": 5}},
    "玄铁剑": {"name": "玄铁剑", "type": "equipment", "slot": "weapon",
             "tier": "灵", "bonus": {"atk": 38, "crit": 4}},
    "青木甲": {"name": "青木甲", "type": "equipment", "slot": "armor",
             "tier": "灵", "bonus": {"hp": 160, "df": 28}},
    "聚灵佩": {"name": "聚灵佩", "type": "equipment", "slot": "accessory",
             "tier": "宝", "bonus": {"mp": 80, "spd": 10}},
    "灵草":   {"name": "灵草",     "type": "material", "sell": 4},
    "玄铁矿": {"name": "玄铁矿",   "type": "material", "sell": 8},
    "兽皮":   {"name": "妖兽皮",   "type": "material", "sell": 5},
    "妖丹":   {"name": "妖丹",     "type": "material", "sell": 18},
    "天材地宝": {"name": "天材地宝", "type": "material", "sell": 80},
    "疗伤丹": {"name": "疗伤丹",   "type": "pill", "sell": 20},
    "补灵丹": {"name": "补灵丹",   "type": "pill", "sell": 20},
    "筑基丹": {"name": "筑基丹",   "type": "pill", "sell": 60},
    "金丹":   {"name": "金丹",     "type": "pill", "sell": 180},
    "元婴丹": {"name": "元婴丹",   "type": "pill", "sell": 500},
    "烈火诀残页": {"name": "烈火诀残页", "type": "page", "skill": "烈火诀", "need": 3},
    "回春术残页": {"name": "回春术残页", "type": "page", "skill": "回春术", "need": 3},
    "玄铁剑图纸": {"name": "玄铁剑图纸", "type": "recipe", "recipe": "forge_sword"},
    "青木甲图纸": {"name": "青木甲图纸", "type": "recipe", "recipe": "forge_armor"},
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
