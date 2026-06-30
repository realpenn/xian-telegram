"""法宝长线 sink 配置（#13）：强化 / 重铸 / 分解。

设计原则：可重复消耗灵石 + 材料；成本随强化等级递增（收益递减）；
多余法宝经分解转为「器魂」，再反哺强化/重铸，形成闭环而非纯卖店。
"""
from __future__ import annotations

ENHANCE_MAX_LEVEL = 10
ENHANCE_PER_LEVEL = 0.08          # 每级提升装备「平加属性」8%（词条/战斗修正不放大）

# 分解产出的器魂（按品阶），外加每级强化返还 1 枚。
DECOMPOSE_QIHUN = {"凡": 1, "灵": 3, "宝": 6, "玄": 10}
QIHUN_KEY = "器魂"

_REFORGE_BASE = {"凡": 60, "灵": 150, "宝": 300, "玄": 520}
_REFORGE_QIHUN = {"凡": 1, "灵": 2, "宝": 3, "玄": 5}


def enhance_cost(level: int) -> dict:
    """第 level→level+1 级强化成本：灵石随级数平方增长（收益递减），器魂随级数增长。"""
    n = level + 1
    return {"stone": 80 * n * n, QIHUN_KEY: 1 + level // 2}


def reforge_cost(tier: str) -> dict:
    """重铸（重 roll 词条）成本：按品阶固定，可重复消耗。"""
    return {"stone": _REFORGE_BASE.get(tier, 100), QIHUN_KEY: _REFORGE_QIHUN.get(tier, 1)}


def decompose_yield(tier: str, enhance_level: int = 0) -> int:
    return DECOMPOSE_QIHUN.get(tier, 1) + max(0, enhance_level)
