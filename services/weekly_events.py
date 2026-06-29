"""周活动副本：绑定材料 + 道行周上限。"""
from __future__ import annotations

import time

from config import weekly_events as CFG
from models import db
from services import activity


def _week(now: int) -> str:
    return time.strftime("%Y-%W", time.localtime(now))


async def run(user_id: int, theme_key: str = "tianmo", now: int = None) -> dict:
    now = int(time.time()) if now is None else now
    theme = CFG.WEEKLY_THEMES.get(theme_key)
    if not theme:
        return {"status": "bad_theme"}
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
