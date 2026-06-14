"""物品定义（静态）。type: weapon/material/pill。"""
from __future__ import annotations

ITEMS = {
    "新手剑": {"name": "新手木剑", "type": "weapon", "tier": "凡", "bonus": {"atk": 5}},
    "灵草":   {"name": "灵草",     "type": "material"},
    "玄铁矿": {"name": "玄铁矿",   "type": "material"},
    "兽皮":   {"name": "妖兽皮",   "type": "material"},
    "妖丹":   {"name": "妖丹",     "type": "material"},
    "筑基丹": {"name": "筑基丹",   "type": "pill"},
    "金丹":   {"name": "金丹",     "type": "pill"},
    "元婴丹": {"name": "元婴丹",   "type": "pill"},
}


def item_name(key: str) -> str:
    it = ITEMS.get(key)
    return it["name"] if it else key


def weapon_bonus(key: str) -> dict:
    it = ITEMS.get(key)
    if it and it.get("type") == "weapon":
        return dict(it.get("bonus", {}))
    return {}
