"""Consumable and recipe item effects."""
from __future__ import annotations

import json
import time

from config import realms as R
from config.items import ITEMS, item_name
from config.recipes import RECIPES
from models import db
from services import character

STAMINA_PILL_GAIN = 40
STAMINA_PILL_DAILY_LIMIT = 2   # 补灵丹每日使用上限，防止绕过精力上限刷钱（#16）
ROOT_BONE_CAP = 100


def _day(ts: int) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(ts))


async def use(user_id: int, item_key: str, now: int = None) -> dict:
    now = int(time.time()) if now is None else now
    item = ITEMS.get(item_key)
    if not item:
        return {"status": "bad_item"}
    async with db.transaction() as conn:
        cur = await conn.execute(
            "SELECT qty FROM inventory WHERE user_id=? AND item_key=?",
            (user_id, item_key))
        inv = await cur.fetchone()
        await cur.close()
        if not inv or inv["qty"] < 1:
            return {"status": "no_item", "item": item_name(item_key)}
        row = await character._select_character(conn, user_id)
        if not row:
            return {"status": "missing"}
        if item.get("type") == "recipe":
            return await _learn_recipe(conn, user_id, item_key, item)
        if item.get("use") == "buff":
            return await _use_buff_pill(conn, user_id, row, item_key, item, now)
        if item_key == "补灵丹":
            return await _use_stamina_pill(conn, user_id, row, now)
        if item_key == "疗伤丹":
            state = json.loads(row["debuff_json"] or "{}")
            state.pop("unstable_until", None)
            await _consume(conn, user_id, item_key)
            await conn.execute(
                "UPDATE characters SET debuff_json=? WHERE user_id=?",
                (json.dumps(state, ensure_ascii=False), user_id))
            return {"status": "healed", "item": item_name(item_key)}
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
    await conn.execute(
        "UPDATE inventory SET qty = MAX(0, qty - 1) WHERE user_id=? AND item_key=?",
        (user_id, item_key))


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


async def _use_stamina_pill(conn, user_id: int, row, now: int) -> dict:
    day = _day(now)
    used = row["pill_stamina_count"] if row["pill_stamina_day"] == day else 0
    if used >= STAMINA_PILL_DAILY_LIMIT:
        return {"status": "pill_limit", "limit": STAMINA_PILL_DAILY_LIMIT}
    welfare = await character._sect_welfare(conn, user_id)
    stamina, stamina_at = character._settled_stamina(row, now, welfare)
    cap = R.STAMINA_CAP[row["realm"]] + welfare["stamina_bonus"]
    gained = min(STAMINA_PILL_GAIN, cap - stamina)
    if gained <= 0:
        return {"status": "stamina_full", "cap": cap}
    await _consume(conn, user_id, "补灵丹")
    await conn.execute(
        "UPDATE characters SET stamina=?, stamina_at=?, pill_stamina_count=?, pill_stamina_day=? "
        "WHERE user_id=?",
        (stamina + gained, stamina_at, used + 1, day, user_id))
    return {"status": "stamina_ok", "gain": gained, "stamina": stamina + gained,
            "cap": cap, "nth": used + 1, "limit": STAMINA_PILL_DAILY_LIMIT}
