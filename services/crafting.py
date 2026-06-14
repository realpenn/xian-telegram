"""炼丹 / 炼器：定时制造、惰性收取、灵石加速（spec §8）。"""
from __future__ import annotations

import json
import random
import time

from config.items import ITEMS, item_name
from config.recipes import ACCELERATE_STONE_PER_MINUTE, RECIPES
from models import db


def _roll_affixes(base_key: str, root_bone: int, prof: int, rng=None) -> dict:
    rng = rng or random.Random()
    pool = ["atk", "hp", "df", "mp", "spd", "crit"]
    rolls = 1 + int(root_bone >= 70) + int(prof >= 5)
    affixes = {}
    for key in rng.sample(pool, min(rolls, len(pool))):
        affixes[key] = rng.randint(4, 12) + prof
    return affixes


async def active_job(user_id: int):
    return await db.fetchone(
        "SELECT * FROM crafting_jobs WHERE user_id=? AND status='active' ORDER BY id LIMIT 1",
        (user_id,))


async def collect_ready(user_id: int, now: int = None) -> list:
    now = int(time.time()) if now is None else now
    collected = []
    async with db.transaction() as conn:
        cur = await conn.execute(
            "SELECT * FROM crafting_jobs WHERE user_id=? AND status='active' AND finish_at<=? "
            "ORDER BY finish_at",
            (user_id, now))
        jobs = await cur.fetchall()
        await cur.close()
        if not jobs:
            return collected
        cur = await conn.execute("SELECT * FROM characters WHERE user_id=?", (user_id,))
        char = await cur.fetchone()
        await cur.close()
        for job in jobs:
            recipe = RECIPES[job["recipe_key"]]
            output = recipe["output"]
            if output["kind"] == "equipment":
                base_key = output["key"]
                item = ITEMS[base_key]
                prof = char["forge_prof"] if recipe["type"] == "forge" else char["alchemy_prof"]
                affixes = _roll_affixes(base_key, char["root_bone"], prof)
                await conn.execute(
                    "INSERT INTO item_instances(user_id, base_key, tier, affixes_json) "
                    "VALUES(?,?,?,?)",
                    (user_id, base_key, item.get("tier", "凡"),
                     json.dumps(affixes, ensure_ascii=False)))
                collected.append({"kind": "equipment", "name": item_name(base_key)})
            else:
                await conn.execute(
                    "INSERT INTO inventory(user_id, item_key, qty) VALUES(?,?,?) "
                    "ON CONFLICT(user_id, item_key) DO UPDATE SET qty = qty + ?",
                    (user_id, output["key"], output["qty"], output["qty"]))
                collected.append({"kind": "item", "name": item_name(output["key"]), "qty": output["qty"]})
            column = "alchemy_prof" if recipe["type"] == "alchemy" else "forge_prof"
            await conn.execute(
                f"UPDATE characters SET {column} = {column} + 1 WHERE user_id=?",
                (user_id,))
            await conn.execute("UPDATE crafting_jobs SET status='done' WHERE id=?", (job["id"],))
    return collected


async def start_job(user_id: int, recipe_key: str, now: int = None) -> dict:
    now = int(time.time()) if now is None else now
    recipe = RECIPES.get(recipe_key)
    if not recipe:
        return {"status": "bad_recipe"}
    await collect_ready(user_id, now)
    async with db.transaction() as conn:
        cur = await conn.execute("SELECT * FROM characters WHERE user_id=?", (user_id,))
        char = await cur.fetchone()
        await cur.close()
        if not char:
            return {"status": "missing"}
        if char["seclusion_at"]:
            return {"status": "in_seclusion"}
        if char["realm"] < recipe["realm"]:
            return {"status": "locked"}
        cur = await conn.execute(
            "SELECT 1 FROM crafting_jobs WHERE user_id=? AND status='active'", (user_id,))
        busy = await cur.fetchone()
        await cur.close()
        if busy:
            return {"status": "busy"}
        if char["spirit_stone"] < recipe["stone"]:
            return {"status": "no_stone", "need": recipe["stone"], "have": char["spirit_stone"]}
        for key, qty in recipe["materials"].items():
            cur = await conn.execute(
                "SELECT qty FROM inventory WHERE user_id=? AND item_key=?", (user_id, key))
            inv = await cur.fetchone()
            await cur.close()
            if not inv or inv["qty"] < qty:
                return {"status": "no_material", "item": key, "need": qty, "have": inv["qty"] if inv else 0}
        await conn.execute(
            "UPDATE characters SET spirit_stone = spirit_stone - ? WHERE user_id=?",
            (recipe["stone"], user_id))
        for key, qty in recipe["materials"].items():
            await conn.execute(
                "UPDATE inventory SET qty = MAX(0, qty - ?) WHERE user_id=? AND item_key=?",
                (qty, user_id, key))
        finish_at = now + recipe["seconds"]
        await conn.execute(
            "INSERT INTO crafting_jobs(user_id, craft_type, recipe_key, start_at, finish_at, status) "
            "VALUES(?,?,?,?,?,'active')",
            (user_id, recipe["type"], recipe_key, now, finish_at))
        return {"status": "started", "name": recipe["name"], "finish_at": finish_at,
                "seconds": recipe["seconds"]}


async def accelerate(user_id: int, now: int = None) -> dict:
    now = int(time.time()) if now is None else now
    async with db.transaction() as conn:
        cur = await conn.execute(
            "SELECT * FROM crafting_jobs WHERE user_id=? AND status='active' ORDER BY id LIMIT 1",
            (user_id,))
        job = await cur.fetchone()
        await cur.close()
        if not job:
            return {"status": "no_job"}
        remaining = max(0, job["finish_at"] - now)
        cost = max(1, (remaining + 59) // 60) * ACCELERATE_STONE_PER_MINUTE
        cur = await conn.execute("SELECT spirit_stone FROM characters WHERE user_id=?", (user_id,))
        char = await cur.fetchone()
        await cur.close()
        if char["spirit_stone"] < cost:
            return {"status": "no_stone", "need": cost, "have": char["spirit_stone"]}
        await conn.execute(
            "UPDATE characters SET spirit_stone = spirit_stone - ? WHERE user_id=?",
            (cost, user_id))
        await conn.execute("UPDATE crafting_jobs SET finish_at=? WHERE id=?", (now, job["id"]))
    return {"status": "accelerated", "cost": cost, "collected": await collect_ready(user_id, now)}
