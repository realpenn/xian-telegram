"""NPC 商店与回收（spec §9）。"""
from __future__ import annotations

from config.items import item_name, sell_price
from config.shop import SHOP_ITEMS
from config import realms as R
from models import db

STAMINA_STONE_COST = 80
STAMINA_STONE_GAIN = 20


async def buy(user_id: int, item_key: str, qty: int = 1) -> dict:
    good = SHOP_ITEMS.get(item_key)
    if not good or qty <= 0:
        return {"status": "bad_item"}
    async with db.transaction() as conn:
        cur = await conn.execute("SELECT realm, spirit_stone FROM characters WHERE user_id=?", (user_id,))
        char = await cur.fetchone()
        await cur.close()
        if not char:
            return {"status": "missing"}
        if char["realm"] < good["realm"]:
            return {"status": "locked"}
        cost = good["price"] * qty
        if char["spirit_stone"] < cost:
            return {"status": "no_stone", "need": cost, "have": char["spirit_stone"]}
        await conn.execute(
            "UPDATE characters SET spirit_stone = spirit_stone - ? WHERE user_id=?",
            (cost, user_id))
        await conn.execute(
            "INSERT INTO inventory(user_id, item_key, qty) VALUES(?,?,?) "
            "ON CONFLICT(user_id, item_key) DO UPDATE SET qty = qty + ?",
            (user_id, item_key, qty, qty))
        return {"status": "ok", "item": item_name(item_key), "qty": qty, "cost": cost}


async def sell(user_id: int, item_key: str, qty: int = 1) -> dict:
    price = sell_price(item_key)
    if price <= 0 or qty <= 0:
        return {"status": "bad_item"}
    async with db.transaction() as conn:
        cur = await conn.execute(
            "SELECT qty FROM inventory WHERE user_id=? AND item_key=?", (user_id, item_key))
        inv = await cur.fetchone()
        await cur.close()
        if not inv or inv["qty"] < qty:
            return {"status": "no_item", "item": item_name(item_key), "have": inv["qty"] if inv else 0}
        gain = price * qty
        await conn.execute(
            "UPDATE inventory SET qty = MAX(0, qty - ?) WHERE user_id=? AND item_key=?",
            (qty, user_id, item_key))
        await conn.execute(
            "UPDATE characters SET spirit_stone = spirit_stone + ? WHERE user_id=?",
            (gain, user_id))
        return {"status": "ok", "item": item_name(item_key), "qty": qty, "gain": gain}


async def buy_stamina(user_id: int, now: int = None) -> dict:
    async with db.transaction() as conn:
        row = await conn.execute("SELECT * FROM characters WHERE user_id=?", (user_id,))
        char = await row.fetchone()
        await row.close()
        if not char:
            return {"status": "missing"}
        from services import character
        welfare = await character._sect_welfare(conn, user_id)
        stamina, stamina_at = character._settled_stamina(char, now, welfare)
        cap = R.STAMINA_CAP[char["realm"]] + welfare["stamina_bonus"]
        if stamina >= cap:
            return {"status": "stamina_full", "cap": cap}
        if char["spirit_stone"] < STAMINA_STONE_COST:
            return {"status": "no_stone", "need": STAMINA_STONE_COST,
                    "have": char["spirit_stone"]}
        gained = min(STAMINA_STONE_GAIN, cap - stamina)
        await conn.execute(
            "UPDATE characters SET spirit_stone=spirit_stone-?, stamina=?, stamina_at=? "
            "WHERE user_id=?",
            (STAMINA_STONE_COST, stamina + gained, stamina_at, user_id))
        return {"status": "stamina_ok", "cost": STAMINA_STONE_COST,
                "gain": gained, "stamina": stamina + gained, "cap": cap}
