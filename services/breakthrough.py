"""突破：小突破自动；大突破需突破丹 + 成功率（金丹起渡天劫）。

失败=损失部分当前修为、**不跌境**（spec §4.3，轻惩罚）。
"""
from __future__ import annotations

import json
import random
import time

from config.items import ITEMS
from config.realms import (BIG_BREAKTHROUGH, advance_cost, is_big_breakthrough,
                           next_stage, realm_label, base_stats)
from models import db

FAIL_CULT_LOSS = 0.30
UNSTABLE_SECONDS = 6 * 3600


def big_success_rate(realm: int, root_bone: int, pill_bonus: float = 0.0) -> float:
    """跨入 realm+1 大境界的成功率，受根骨/丹药修正，限 [0.05, 0.95]。"""
    base = BIG_BREAKTHROUGH[realm + 1]["base_rate"]
    rate = base + (root_bone - 50) * 0.003 + pill_bonus
    return max(0.05, min(0.95, rate))


def tribulation_trial(source_realm: int, source_stage: int, root_bone: int,
                      guard_bonus: int = 0, rng=None) -> dict:
    rng = rng or random
    stats = base_stats(source_realm, source_stage)
    hp = stats["hp"]
    shield = int(stats["df"] * 0.6 + root_bone * 2 + guard_bonus)
    log = []
    for idx in range(1, 4):
        raw = int((stats["hp"] * 0.18 + stats["df"] * 1.8) * (0.9 + rng.random() * 0.2))
        dmg = max(1, raw - shield)
        hp -= dmg
        log.append(f"第 {idx} 道雷劫落下，承伤 {dmg}")
        if hp <= 0:
            return {"survived": False, "log": log}
    return {"survived": True, "log": log}


async def _breakthrough_mods(conn, user_id: int) -> dict:
    cur = await conn.execute(
        "SELECT base_key, affixes_json FROM item_instances "
        "WHERE user_id=? AND equipped_slot IS NOT NULL",
        (user_id,))
    rows = await cur.fetchall()
    await cur.close()
    rate = 0.0
    guard = 0
    for row in rows:
        item = ITEMS.get(row["base_key"], {})
        rate += float(item.get("breakthrough_rate", 0.0))
        guard += int(item.get("tribulation_shield", 0))
    cur = await conn.execute(
        "SELECT skill_key FROM character_skills WHERE user_id=? AND slot>=0",
        (user_id,))
    skills = {row["skill_key"] for row in await cur.fetchall()}
    await cur.close()
    if "金钟罩" in skills:
        guard += 120
    return {"rate": rate, "guard": guard}


async def _fail(conn, user_id: int, cultivation: int, rate: float, trib: bool,
                loss: int = None, tribulation_log=None, now: int = None):
    now = int(time.time()) if now is None else now
    loss = int(cultivation * FAIL_CULT_LOSS) if loss is None else loss
    debuff = json.dumps({"unstable_until": now + UNSTABLE_SECONDS}, ensure_ascii=False)
    await conn.execute(
        "UPDATE characters SET cultivation=?, debuff_json=? WHERE user_id=?",
        (max(0, cultivation - loss), debuff, user_id))
    return {"status": "big_fail", "rate": rate, "tribulation": trib, "loss": loss,
            "tribulation_log": tribulation_log or [],
            "debuff_seconds": UNSTABLE_SECONDS}


async def try_advance(user_id: int) -> dict:
    now = int(time.time())
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
            mods = await _breakthrough_mods(conn, user_id)
            rate = big_success_rate(char["realm"], char["root_bone"], mods["rate"])
            trib = BIG_BREAKTHROUGH[target]["tribulation"]
            if random.random() >= rate:
                return await _fail(conn, user_id, char["cultivation"], rate, trib, now=now)
            tribulation = {"survived": True, "log": []}
            if trib:
                tribulation = tribulation_trial(
                    char["realm"], char["stage"], char["root_bone"], mods["guard"])
            if tribulation["survived"]:
                await conn.execute(
                    "UPDATE characters SET realm=?, stage=?, cultivation=?, debuff_json='{}' "
                    "WHERE user_id=?",
                    (nxt[0], nxt[1], max(0, char["cultivation"] - cost), user_id))
                return {"status": "big_success", "rate": rate, "tribulation": trib,
                        "label": realm_label(nxt[0], nxt[1]),
                        "tribulation_log": tribulation["log"]}
            return await _fail(
                conn, user_id, char["cultivation"], rate, trib,
                tribulation_log=tribulation["log"], now=now)

        await conn.execute(
            "UPDATE characters SET realm=?, stage=?, cultivation=?, debuff_json='{}' WHERE user_id=?",
            (nxt[0], nxt[1], max(0, char["cultivation"] - cost), user_id))
        return {"status": "small_success", "label": realm_label(nxt[0], nxt[1])}
