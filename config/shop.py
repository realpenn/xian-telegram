"""NPC 商店与回收配置（spec §9）。"""
from __future__ import annotations

SHOP_ITEMS = {
    "灵草": {"price": 12, "realm": 0},
    "玄铁矿": {"price": 24, "realm": 1},
    "兽皮": {"price": 16, "realm": 0},
    "妖丹": {"price": 55, "realm": 1},
    "筑基丹": {"price": 260, "realm": 0},
    "金丹": {"price": 900, "realm": 1},
    "元婴丹": {"price": 2400, "realm": 2},
}


def goods_for_realm(realm: int):
    return [(key, val) for key, val in SHOP_ITEMS.items() if realm >= val["realm"]]
