"""玩家一口价坊市（v2 M5）。"""
from __future__ import annotations

import time

from config.items import item_name
from models import db
from services import character

MARKET_TAX_RATE = 0.05
MIN_PRICE = 1


async def list_active(limit: int = 20) -> list[dict]:
    rows = await db.fetchall(
        "SELECT * FROM market_listings WHERE status='active' ORDER BY created_at LIMIT ?",
        (limit,))
    return [_format(row) for row in rows]


async def create_listing(seller_id: int, item_key: str, qty: int, price: int, now: int = None) -> dict:
    now = int(time.time()) if now is None else now
    qty = int(qty)
    price = int(price)
    if qty <= 0 or price < MIN_PRICE:
        return {"status": "bad_request"}
    async with db.transaction() as conn:
        have = await character.item_qty_conn(conn, seller_id, item_key, bound=0)
        if have < qty:
            return {"status": "no_item", "have": have}
        await character.consume_item_conn(conn, seller_id, item_key, qty, bound=0)
        cur = await conn.execute(
            "INSERT INTO market_listings(seller_id, item_key, qty, price, status, created_at, updated_at) "
            "VALUES(?,?,?,?, 'active', ?, ?)",
            (seller_id, item_key, qty, price, now, now))
        listing_id = cur.lastrowid
        await cur.close()
        return {"status": "ok", "listing_id": listing_id, "item": item_name(item_key),
                "qty": qty, "price": price}


async def buy(buyer_id: int, listing_id: int, now: int = None) -> dict:
    now = int(time.time()) if now is None else now
    async with db.transaction() as conn:
        cur = await conn.execute("SELECT * FROM market_listings WHERE id=?", (listing_id,))
        listing = await cur.fetchone()
        await cur.close()
        if not listing or listing["status"] != "active":
            return {"status": "not_available"}
        if listing["seller_id"] == buyer_id:
            return {"status": "self_buy"}
        cur = await conn.execute("SELECT spirit_stone FROM characters WHERE user_id=?", (buyer_id,))
        buyer = await cur.fetchone()
        await cur.close()
        if not buyer:
            return {"status": "missing"}
        if buyer["spirit_stone"] < listing["price"]:
            return {"status": "no_stone", "need": listing["price"], "have": buyer["spirit_stone"]}
        tax = int(listing["price"] * MARKET_TAX_RATE)
        seller_gain = listing["price"] - tax
        await conn.execute(
            "UPDATE characters SET spirit_stone=spirit_stone-? WHERE user_id=?",
            (listing["price"], buyer_id))
        await conn.execute(
            "UPDATE characters SET spirit_stone=spirit_stone+? WHERE user_id=?",
            (seller_gain, listing["seller_id"]))
        await conn.execute(
            "INSERT INTO inventory(user_id, item_key, bound, qty) VALUES(?,?,0,?) "
            "ON CONFLICT(user_id, item_key, bound) DO UPDATE SET qty=qty+?",
            (buyer_id, listing["item_key"], listing["qty"], listing["qty"]))
        await conn.execute(
            "UPDATE market_listings SET status='sold', buyer_id=?, updated_at=? "
            "WHERE id=? AND status='active'",
            (buyer_id, now, listing_id))
        return {"status": "ok", "item": item_name(listing["item_key"]), "qty": listing["qty"],
                "price": listing["price"], "tax": tax, "seller_gain": seller_gain}


async def cancel(seller_id: int, listing_id: int, now: int = None) -> dict:
    now = int(time.time()) if now is None else now
    async with db.transaction() as conn:
        cur = await conn.execute("SELECT * FROM market_listings WHERE id=?", (listing_id,))
        listing = await cur.fetchone()
        await cur.close()
        if not listing or listing["status"] != "active":
            return {"status": "not_available"}
        if listing["seller_id"] != seller_id:
            return {"status": "forbidden"}
        await conn.execute(
            "UPDATE market_listings SET status='cancelled', updated_at=? WHERE id=?",
            (now, listing_id))
        await conn.execute(
            "INSERT INTO inventory(user_id, item_key, bound, qty) VALUES(?,?,0,?) "
            "ON CONFLICT(user_id, item_key, bound) DO UPDATE SET qty=qty+?",
            (seller_id, listing["item_key"], listing["qty"], listing["qty"]))
        return {"status": "ok", "item": item_name(listing["item_key"]), "qty": listing["qty"]}


async def audit_suspicious(limit_price: int = 1_000_000) -> list[dict]:
    rows = await db.fetchall(
        "SELECT * FROM market_listings WHERE price>=? ORDER BY price DESC",
        (limit_price,))
    return [_format(row) for row in rows]


def _format(row) -> dict:
    return {
        "id": row["id"],
        "seller_id": row["seller_id"],
        "buyer_id": row["buyer_id"],
        "item_key": row["item_key"],
        "item": item_name(row["item_key"]),
        "qty": row["qty"],
        "price": row["price"],
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
