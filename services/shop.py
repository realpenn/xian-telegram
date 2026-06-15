"""NPC 商店与回收（spec §9）。"""
from __future__ import annotations

import time

from config.items import item_name, sell_price
from config.shop import (SHOP_ITEMS, STAMINA_BUY_DAILY_LIMIT, STAMINA_BUY_GAIN,
                         stamina_buy_cost)
from config import realms as R
from models import db


def _day(ts: int) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(ts))


def first_buy_cost_per_stamina(realm: int) -> float:
    """当日首买的单位精力灵石成本（用于经济模拟/校准）。"""
    return stamina_buy_cost(realm, 1) / STAMINA_BUY_GAIN


async def stamina_buy_offer(user_id: int, now: int = None) -> dict:
    """返回当前商店应展示的下一次买精力价格。"""
    now = int(time.time()) if now is None else now
    day = _day(now)
    row = await db.fetchone(
        "SELECT realm, stamina_buy_count, stamina_buy_day FROM characters WHERE user_id=?",
        (user_id,))
    if not row:
        return {"status": "missing"}
    bought = row["stamina_buy_count"] if row["stamina_buy_day"] == day else 0
    if bought >= STAMINA_BUY_DAILY_LIMIT:
        return {"status": "buy_limit", "bought": bought,
                "limit": STAMINA_BUY_DAILY_LIMIT, "gain": STAMINA_BUY_GAIN}
    nth = bought + 1
    return {"status": "ok", "cost": stamina_buy_cost(row["realm"], nth),
            "gain": STAMINA_BUY_GAIN, "nth": nth,
            "limit": STAMINA_BUY_DAILY_LIMIT}


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
    now = int(time.time()) if now is None else now
    day = _day(now)
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
        # 当日购买次数（跨天重置）。
        bought = char["stamina_buy_count"] if char["stamina_buy_day"] == day else 0
        if bought >= STAMINA_BUY_DAILY_LIMIT:
            return {"status": "buy_limit", "limit": STAMINA_BUY_DAILY_LIMIT}
        nth = bought + 1
        cost = stamina_buy_cost(char["realm"], nth)
        if char["spirit_stone"] < cost:
            return {"status": "no_stone", "need": cost, "have": char["spirit_stone"]}
        gained = min(STAMINA_BUY_GAIN, cap - stamina)
        await conn.execute(
            "UPDATE characters SET spirit_stone=spirit_stone-?, stamina=?, stamina_at=?, "
            "stamina_buy_count=?, stamina_buy_day=? WHERE user_id=?",
            (cost, stamina + gained, stamina_at, nth, day, user_id))
        return {"status": "stamina_ok", "cost": cost, "gain": gained,
                "stamina": stamina + gained, "cap": cap, "nth": nth,
                "limit": STAMINA_BUY_DAILY_LIMIT,
                "next_cost": stamina_buy_cost(char["realm"], nth + 1)
                if nth < STAMINA_BUY_DAILY_LIMIT else None}
