"""突破：小突破自动；大突破需突破丹 + 成功率（金丹起渡天劫）。

失败=损失部分当前修为、**不跌境**（spec §4.3，轻惩罚）。
"""
from __future__ import annotations

import random

from config.realms import (BIG_BREAKTHROUGH, advance_cost, is_big_breakthrough,
                           next_stage, realm_label)
from models import db

FAIL_CULT_LOSS = 0.30


def big_success_rate(realm: int, root_bone: int, pill_bonus: float = 0.0) -> float:
    """跨入 realm+1 大境界的成功率，受根骨/丹药修正，限 [0.05, 0.95]。"""
    base = BIG_BREAKTHROUGH[realm + 1]["base_rate"]
    rate = base + (root_bone - 50) * 0.003 + pill_bonus
    return max(0.05, min(0.95, rate))


async def try_advance(user_id: int) -> dict:
    async with db.transaction() as conn:
        cur = await conn.execute("SELECT * FROM characters WHERE user_id=?", (user_id,))
        char = await cur.fetchone()
        await cur.close()
        if not char:
            return {"status": "missing"}
        if char["seclusion_at"]:
            return {"status": "in_seclusion"}

        cost = advance_cost(char["realm"], char["stage"])
        if char["cultivation"] < cost:
            return {"status": "need_cult", "need": cost - char["cultivation"]}
        nxt = next_stage(char["realm"], char["stage"])
        if nxt is None:
            return {"status": "at_cap"}

        if is_big_breakthrough(char["realm"], char["stage"]):
            target = char["realm"] + 1
            pill = BIG_BREAKTHROUGH[target]["pill"]
            cur = await conn.execute(
                "SELECT qty FROM inventory WHERE user_id=? AND item_key=?", (user_id, pill))
            item = await cur.fetchone()
            await cur.close()
            if not item or item["qty"] < 1:
                return {"status": "need_pill", "pill": pill}
            await conn.execute(
                "UPDATE inventory SET qty = MAX(0, qty - 1) "
                "WHERE user_id=? AND item_key=?",
                (user_id, pill))
            rate = big_success_rate(char["realm"], char["root_bone"])
            trib = BIG_BREAKTHROUGH[target]["tribulation"]
            if random.random() < rate:
                await conn.execute(
                    "UPDATE characters SET realm=?, stage=?, cultivation=? WHERE user_id=?",
                    (nxt[0], nxt[1], max(0, char["cultivation"] - cost), user_id))
                return {"status": "big_success", "rate": rate, "tribulation": trib,
                        "label": realm_label(nxt[0], nxt[1])}
            loss = int(char["cultivation"] * FAIL_CULT_LOSS)
            await conn.execute(
                "UPDATE characters SET cultivation=? WHERE user_id=?",
                (max(0, char["cultivation"] - loss), user_id))
            return {"status": "big_fail", "rate": rate, "tribulation": trib, "loss": loss}

        await conn.execute(
            "UPDATE characters SET realm=?, stage=?, cultivation=? WHERE user_id=?",
            (nxt[0], nxt[1], max(0, char["cultivation"] - cost), user_id))
        return {"status": "small_success", "label": realm_label(nxt[0], nxt[1])}
