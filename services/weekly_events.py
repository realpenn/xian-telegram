"""周活动副本：绑定材料 + 道行周上限。"""
from __future__ import annotations

import time

from config import weekly_events as CFG
from models import db
from services import activity


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
        cur = await conn.execute("SELECT stamina FROM characters WHERE user_id=?", (user_id,))
        ch = await cur.fetchone()
        await cur.close()
        if not ch:
            return {"status": "missing"}
        if ch["stamina"] < CFG.RUN_STAMINA_COST:
            return {"status": "no_stamina", "need": CFG.RUN_STAMINA_COST, "have": ch["stamina"]}
        cur = await conn.execute(
            "SELECT daohang FROM weekly_activity WHERE user_id=? AND week=?",
            (user_id, week))
        row = await cur.fetchone()
        await cur.close()
        used = row["daohang"] if row else 0
        daohang = min(CFG.RUN_DAOHANG_REWARD, max(0, CFG.WEEKLY_DAOHANG_CAP - used))
        await conn.execute(
            "UPDATE characters SET stamina=stamina-?, daohang=daohang+? WHERE user_id=?",
            (CFG.RUN_STAMINA_COST, daohang, user_id))
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
