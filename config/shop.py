"""NPC 商店与回收配置（spec §9）。"""
from __future__ import annotations

SHOP_ITEMS = {
    "灵草": {"price": 12, "realm": 0},
    "玄铁矿": {"price": 24, "realm": 1},
    "兽皮": {"price": 16, "realm": 0},
    "妖丹": {"price": 55, "realm": 1},
    "虎力丹": {"price": 120, "realm": 0},
    "凝神丹": {"price": 120, "realm": 0},
    "筑基丹": {"price": 260, "realm": 0},
    "金丹": {"price": 900, "realm": 1},
    "元婴丹": {"price": 2400, "realm": 2},
    "洗髓丹": {"price": 900, "realm": 2},
    "玄铁剑图纸": {"price": 220, "realm": 1},
    "青木甲图纸": {"price": 260, "realm": 1},
    "洗髓丹丹方": {"price": 420, "realm": 2},
    "聚灵佩图纸": {"price": 460, "realm": 2},
}


def goods_for_realm(realm: int):
    return [(key, val) for key, val in SHOP_ITEMS.items() if realm >= val["realm"]]


# 灵石买精力（#16）：按境界基价 + 当日第 n 次翻倍递增 + 每日封顶，
# 让首买单价就高于当前最佳内容的灵石/精力产出，堵死 灵石→精力→刷钱 套利。
STAMINA_BUY_BASE = {0: 120, 1: 260, 2: 600, 3: 1200}
STAMINA_BUY_DAILY_LIMIT = 3
STAMINA_BUY_GAIN = 20


def stamina_buy_cost(realm: int, nth: int) -> int:
    """当日第 nth 次（1-indexed）买精力的灵石价：基价 × 2^(n-1)。"""
    base = STAMINA_BUY_BASE.get(realm, STAMINA_BUY_BASE[max(STAMINA_BUY_BASE)])
    return base * (2 ** max(0, nth - 1))
