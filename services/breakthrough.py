"""突破：小突破自动；大突破需突破丹 + 成功率（金丹起渡天劫）。

失败=损失部分当前修为、**不跌境**（spec §4.3，轻惩罚）。
"""
from __future__ import annotations

import random

from config.realms import (BIG_BREAKTHROUGH, advance_cost, is_big_breakthrough,
                           next_stage, realm_label)
from services import character

FAIL_CULT_LOSS = 0.30


def big_success_rate(realm: int, root_bone: int, pill_bonus: float = 0.0) -> float:
    """跨入 realm+1 大境界的成功率，受根骨/丹药修正，限 [0.05, 0.95]。"""
    base = BIG_BREAKTHROUGH[realm + 1]["base_rate"]
    rate = base + (root_bone - 50) * 0.003 + pill_bonus
    return max(0.05, min(0.95, rate))


async def try_advance(user_id: int) -> dict:
    char = await character.get(user_id)
    cost = advance_cost(char.realm, char.stage)
    if char.cultivation < cost:
        return {"status": "need_cult", "need": cost - char.cultivation}
    nxt = next_stage(char.realm, char.stage)
    if nxt is None:
        return {"status": "at_cap"}

    if is_big_breakthrough(char.realm, char.stage):
        target = char.realm + 1
        pill = BIG_BREAKTHROUGH[target]["pill"]
        if await character.item_qty(user_id, pill) < 1:
            return {"status": "need_pill", "pill": pill}
        await character.add_item(user_id, pill, -1)
        rate = big_success_rate(char.realm, char.root_bone)
        trib = BIG_BREAKTHROUGH[target]["tribulation"]
        if random.random() < rate:
            await character.set_progress(user_id, nxt[0], nxt[1], char.cultivation - cost)
            return {"status": "big_success", "rate": rate, "tribulation": trib,
                    "label": realm_label(nxt[0], nxt[1])}
        loss = int(char.cultivation * FAIL_CULT_LOSS)
        await character.set_cultivation(user_id, char.cultivation - loss)
        return {"status": "big_fail", "rate": rate, "tribulation": trib, "loss": loss}

    await character.set_progress(user_id, nxt[0], nxt[1], char.cultivation - cost)
    return {"status": "small_success", "label": realm_label(nxt[0], nxt[1])}
