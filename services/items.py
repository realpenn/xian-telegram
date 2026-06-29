"""Consumable and recipe item effects."""
from __future__ import annotations

import json
import time

from config.items import ITEMS, item_name
from config.recipes import RECIPES
from models import db
from services import character

ROOT_BONE_CAP = 100
# 回复类丹药（#24）：按 max 的百分比补当前血蓝；疗伤丹兼清「道基不稳」。
# 补灵丹由「回精力」改为「回法力」，买精力仍走 shop.stamina_buy_cost。
RESTORE_PILLS = {
    "疗伤丹": {"hp": 0.50, "mp": 0.0, "clear_unstable": True},
    "补灵丹": {"hp": 0.0, "mp": 0.50, "clear_unstable": False},
    "大还丹": {"hp": 1.0, "mp": 1.0, "clear_unstable": False},
}


async def use(user_id: int, item_key: str, now: int = None) -> dict:
    now = int(time.time()) if now is None else now
    item = ITEMS.get(item_key)
    if not item:
        return {"status": "bad_item"}
    async with db.transaction() as conn:
        have = await character.item_qty_conn(conn, user_id, item_key)
        if have < 1:
            return {"status": "no_item", "item": item_name(item_key)}
        row = await character._select_character(conn, user_id)
        if not row:
            return {"status": "missing"}
        if item.get("type") == "recipe":
            return await _learn_recipe(conn, user_id, item_key, item)
        if item.get("use") == "buff":
            return await _use_buff_pill(conn, user_id, row, item_key, item, now)
        if item_key in RESTORE_PILLS:
            return await _use_restore_pill(conn, user_id, row, item_key, now)
        if item_key in ("天材地宝", "洗髓丹"):
            gain = 1 if item_key == "天材地宝" else 3
            new_root = min(ROOT_BONE_CAP, row["root_bone"] + gain)
            if new_root == row["root_bone"]:
                return {"status": "root_cap", "cap": ROOT_BONE_CAP}
            await _consume(conn, user_id, item_key)
            await conn.execute(
                "UPDATE characters SET root_bone=? WHERE user_id=?",
                (new_root, user_id))
            return {"status": "root_up", "item": item_name(item_key),
                    "old": row["root_bone"], "new": new_root}
    return {"status": "not_usable", "item": item_name(item_key)}


async def _consume(conn, user_id: int, item_key: str):
    await character.consume_item_conn(conn, user_id, item_key, 1)


async def _learn_recipe(conn, user_id: int, item_key: str, item: dict) -> dict:
    recipe_key = item.get("recipe")
    recipe = RECIPES.get(recipe_key)
    if not recipe:
        return {"status": "bad_recipe"}
    cur = await conn.execute(
        "SELECT 1 FROM recipes_known WHERE user_id=? AND recipe_key=?",
        (user_id, recipe_key))
    known = await cur.fetchone()
    await cur.close()
    if recipe.get("default", False) or known:
        return {"status": "known_recipe", "recipe": recipe["name"]}
    await _consume(conn, user_id, item_key)
    await conn.execute(
        "INSERT OR IGNORE INTO recipes_known(user_id, recipe_key) VALUES(?,?)",
        (user_id, recipe_key))
    return {"status": "recipe_ok", "item": item_name(item_key), "recipe": recipe["name"]}


async def _use_buff_pill(conn, user_id: int, row, item_key: str, item: dict, now: int) -> dict:
    effects = dict(item.get("buff") or {})
    duration = int(item.get("duration", 0))
    if not effects or duration <= 0:
        return {"status": "not_usable", "item": item_name(item_key)}
    state = json.loads(row["debuff_json"] or "{}")
    buffs = state.setdefault("buffs", {})
    until = now + duration
    buffs[item_key] = {"until": until, "effects": effects}
    await _consume(conn, user_id, item_key)
    await conn.execute(
        "UPDATE characters SET debuff_json=? WHERE user_id=?",
        (json.dumps(state, ensure_ascii=False), user_id))
    return {
        "status": "buff_ok",
        "item": item_name(item_key),
        "effects": effects,
        "duration": duration,
        "until": until,
    }


async def _use_restore_pill(conn, user_id: int, row, item_key: str, now: int) -> dict:
    """回血/回蓝/补满丹（#24）：按 max 百分比补当前血蓝。

    P3：疗伤丹若要清「道基不稳」，先把它从状态里清掉再算 stats，使回血与写回
    都基于「未被压制」的真实 max，避免满血角色被清成 180/200。
    """
    # 有未领取的历练/秘境时禁服恢复丹（#24 P1）：战斗结算→自然回复有严格事件顺序，
    # 必须先领取把战斗结果落库，才能正确叠加丹药；否则会出现"事后扣伤害/丹药被覆盖"。
    if await character._has_active_job(conn, user_id):
        return {"status": "busy_activity", "item": item_name(item_key)}
    spec = RESTORE_PILLS[item_key]
    char = character._from_row(row)
    will_clear = spec["clear_unstable"] and int(char.debuff_json.get("unstable_until", 0)) > now
    if will_clear:
        char.debuff_json.pop("unstable_until", None)
    st = await character.stats(char)
    max_hp, max_mp = st["hp"], st["mp"]
    cur_hp, _, cur_mp, _ = character.settled_vitals(char, max_hp, max_mp, now)
    new_hp = min(max_hp, cur_hp + int(max_hp * spec["hp"]))
    new_mp = min(max_mp, cur_mp + int(max_mp * spec["mp"]))
    hp_gain, mp_gain = new_hp - cur_hp, new_mp - cur_mp
    if hp_gain <= 0 and mp_gain <= 0 and not will_clear:
        return {"status": "vital_full", "item": item_name(item_key)}
    await _consume(conn, user_id, item_key)
    if will_clear:
        await conn.execute(
            "UPDATE characters SET debuff_json=? WHERE user_id=?",
            (json.dumps(char.debuff_json, ensure_ascii=False), user_id))
    await character.write_vitals(user_id, new_hp, new_mp, now, conn=conn)
    return {"status": "vital_restored", "item": item_name(item_key),
            "hp": new_hp, "max_hp": max_hp, "mp": new_mp, "max_mp": max_mp,
            "hp_gain": hp_gain, "mp_gain": mp_gain, "cleared_unstable": will_clear}
