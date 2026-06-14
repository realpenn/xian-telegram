"""炼丹 / 炼器配方（静态配置，spec §8）。"""
from __future__ import annotations

RECIPES = {
    "heal_pill": {
        "name": "疗伤丹", "type": "alchemy", "realm": 1, "seconds": 20,
        "stone": 25, "materials": {"灵草": 3}, "output": {"kind": "item", "key": "疗伤丹", "qty": 1},
        "default": True,
    },
    "stamina_pill": {
        "name": "补灵丹", "type": "alchemy", "realm": 1, "seconds": 20,
        "stone": 30, "materials": {"灵草": 2, "妖丹": 1},
        "output": {"kind": "item", "key": "补灵丹", "qty": 1}, "default": True,
    },
    "might_pill": {
        "name": "虎力丹", "type": "alchemy", "realm": 1, "seconds": 20,
        "stone": 35, "materials": {"灵草": 2, "兽皮": 1},
        "output": {"kind": "item", "key": "虎力丹", "qty": 1}, "default": True,
    },
    "focus_pill": {
        "name": "凝神丹", "type": "alchemy", "realm": 1, "seconds": 20,
        "stone": 35, "materials": {"灵草": 3},
        "output": {"kind": "item", "key": "凝神丹", "qty": 1}, "default": True,
    },
    "foundation_pill": {
        "name": "筑基丹", "type": "alchemy", "realm": 1, "seconds": 30,
        "stone": 80, "materials": {"灵草": 5, "妖丹": 2},
        "output": {"kind": "item", "key": "筑基丹", "qty": 1}, "default": True,
    },
    "marrow_pill": {
        "name": "洗髓丹", "type": "alchemy", "realm": 2, "seconds": 45,
        "stone": 120, "materials": {"天材地宝": 1, "妖丹": 3},
        "output": {"kind": "item", "key": "洗髓丹", "qty": 1}, "default": False,
    },
    "forge_sword": {
        "name": "玄铁剑", "type": "forge", "realm": 1, "seconds": 30,
        "stone": 80, "materials": {"玄铁矿": 5, "兽皮": 2},
        "output": {"kind": "equipment", "key": "玄铁剑"}, "default": True,
    },
    "forge_armor": {
        "name": "青木甲", "type": "forge", "realm": 1, "seconds": 30,
        "stone": 90, "materials": {"灵草": 4, "兽皮": 5},
        "output": {"kind": "equipment", "key": "青木甲"}, "default": True,
    },
    "forge_accessory": {
        "name": "聚灵佩", "type": "forge", "realm": 2, "seconds": 45,
        "stone": 120, "materials": {"玄铁矿": 4, "妖丹": 2, "天材地宝": 1},
        "output": {"kind": "equipment", "key": "聚灵佩"}, "default": False,
    },
}

ACCELERATE_STONE_PER_MINUTE = 5


def recipes_for_realm(realm: int):
    return [(key, val) for key, val in RECIPES.items() if realm >= val["realm"]]
