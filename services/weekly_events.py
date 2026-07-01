"""周活动副本：绑定材料 + 道行周上限。"""
from __future__ import annotations

import time

from config import weekly_events as CFG
from models import db
from services import activity, ascension, character


async def _activity_material_total(conn, user_id: int) -> int:
    total = 0
    for mat in CFG.ACTIVITY_MATERIALS:
        total += await character.item_qty_conn(conn, user_id, mat)
    return total


async def _consume_activity_materials(conn, user_id: int, need: int):
    """按固定顺序消耗任意活动材料，凑够 need 个。"""
    left = need
    for mat in CFG.ACTIVITY_MATERIALS:
        if left <= 0:
            break
        have = await character.item_qty_conn(conn, user_id, mat)
        if have <= 0:
            continue
        used = min(left, have)
        await character.consume_item_conn(conn, user_id, mat, used)
        left -= used


async def exchange(user_id: int, offer_key: str, now: int = None) -> dict:
    """活动商店：消耗活动材料兑换保命符 / 飞升点（spec §5.4 / T4.1；T3.2 飞升点源之四）。"""
    now = int(time.time()) if now is None else now
    offer = CFG.SHOP_OFFERS.get(offer_key)
    if not offer:
        return {"status": "bad_offer"}
    cost = int(offer["material_cost"])
    async with db.transaction() as conn:
        ch = await character._select_character(conn, user_id)
        if not ch:
            return {"status": "missing"}
        have = await _activity_material_total(conn, user_id)
        if have < cost:
            return {"status": "no_material", "need": cost, "have": have}
        await _consume_activity_materials(conn, user_id, cost)
        if offer["reward_kind"] == "ascension":
            await ascension.add_points_conn(conn, user_id, int(offer["reward_qty"]), now)
            return {"status": "ok", "kind": "ascension", "name": offer["name"],
                    "qty": int(offer["reward_qty"]), "cost": cost}
        # 绑定道具入包（bound=1），与坊市隔离一致。
        await conn.execute(
            "INSERT INTO inventory(user_id, item_key, bound, qty) VALUES(?,?,1,?) "
            "ON CONFLICT(user_id, item_key, bound) DO UPDATE SET qty=qty+?",
            (user_id, offer["reward_item"], int(offer["reward_qty"]), int(offer["reward_qty"])))
        return {"status": "ok", "kind": "item", "name": offer["name"],
                "item": offer["reward_item"], "qty": int(offer["reward_qty"]), "cost": cost}


def _week(now: int) -> str:
    return time.strftime("%Y-%W", time.localtime(now))


def current_theme_key(now: int) -> str:
    """按周确定性轮换：每周仅开放一个主题（防同时刷三种材料肝度失控）。"""
    keys = list(CFG.WEEKLY_THEMES)
    week_no = int(time.strftime("%W", time.localtime(now)))
    return keys[week_no % len(keys)]


async def run(user_id: int, theme_key: str = None, now: int = None) -> dict:
    now = int(time.time()) if now is None else now
    if theme_key is not None and theme_key not in CFG.WEEKLY_THEMES:
        return {"status": "bad_theme"}
    open_key = current_theme_key(now)
    theme_key = theme_key or open_key
    if theme_key != open_key:
        return {"status": "closed", "open": open_key,
                "open_name": CFG.WEEKLY_THEMES[open_key]["name"]}
    theme = CFG.WEEKLY_THEMES[theme_key]
    week = _week(now)
    async with db.transaction() as conn:
        ch = await character._select_character(conn, user_id)
        if not ch:
            return {"status": "missing"}
        welfare = await character._sect_welfare(conn, user_id)
        stamina, stamina_at = character._settled_stamina(ch, now, welfare)
        if stamina < CFG.RUN_STAMINA_COST:
            await conn.execute(
                "UPDATE characters SET stamina=?, stamina_at=? WHERE user_id=?",
                (stamina, stamina_at, user_id))
            return {"status": "no_stamina", "need": CFG.RUN_STAMINA_COST, "have": stamina}
        cur = await conn.execute(
            "SELECT daohang FROM weekly_activity WHERE user_id=? AND week=?",
            (user_id, week))
        row = await cur.fetchone()
        await cur.close()
        used = row["daohang"] if row else 0
        daohang = min(CFG.RUN_DAOHANG_REWARD, max(0, CFG.WEEKLY_DAOHANG_CAP - used))
        await conn.execute(
            "UPDATE characters SET stamina=?, stamina_at=?, daohang=daohang+? WHERE user_id=?",
            (stamina - CFG.RUN_STAMINA_COST, stamina_at, daohang, user_id))
        await conn.execute(
            "INSERT INTO inventory(user_id, item_key, bound, qty) VALUES(?,?,1,?) "
            "ON CONFLICT(user_id, item_key, bound) DO UPDATE SET qty=qty+?",
            (user_id, theme["material"], 1, 1))
        await conn.execute(
            "INSERT INTO weekly_activity(user_id, week, runs, daohang) VALUES(?,?,1,?) "
            "ON CONFLICT(user_id, week) DO UPDATE SET runs=runs+1, daohang=daohang+?",
            (user_id, week, daohang, daohang))
        await activity.record_virtual_window(user_id, "weekly_activity", theme_key, now,
                                             CFG.RUN_DURATION_SECONDS, conn=conn)
        return {"status": "ok", "theme": theme["name"], "daohang": daohang,
                "material": theme["material"], "bound": 1}
