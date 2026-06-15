"""主动提醒：扫描已完成的耗时动作并私聊通知用户。"""
from __future__ import annotations

import logging
import time

from config.dungeons import DUNGEONS
from config.maps import MAPS
from models import db

log = logging.getLogger("xian.notifications")
MAX_NOTIFY_ATTEMPTS = 5


async def notify_ready_actions(bot, now: int = None) -> dict:
    now = int(time.time()) if now is None else now
    explore_count = await _notify_explore(bot, now)
    dungeon_count = await _notify_dungeon(bot, now)
    return {"explore": explore_count, "dungeon": dungeon_count}


async def _notify_explore(bot, now: int) -> int:
    rows = await db.fetchall(
        "SELECT user_id, map_key, notify_attempts FROM explore_runs "
        "WHERE status='active' AND finish_at<=? AND notified_at IS NULL",
        (now,))
    sent = 0
    for row in rows:
        name = MAPS.get(row["map_key"], {}).get("name", row["map_key"])
        if await _send(
            bot, row["user_id"],
            f"⚔️ {name} 历练已完成，发送 /explore 或点击菜单领取结算。"
        ):
            await db.execute(
                "UPDATE explore_runs SET notified_at=? "
                "WHERE user_id=? AND notified_at IS NULL",
                (now, row["user_id"]))
            sent += 1
        else:
            await _record_failure("explore_runs", row["user_id"],
                                  int(row["notify_attempts"] or 0), now)
    return sent


async def _notify_dungeon(bot, now: int) -> int:
    rows = await db.fetchall(
        "SELECT user_id, dungeon_key, notify_attempts FROM dungeon_jobs "
        "WHERE status='active' AND finish_at<=? AND notified_at IS NULL",
        (now,))
    sent = 0
    for row in rows:
        name = DUNGEONS.get(row["dungeon_key"], {}).get("name", row["dungeon_key"])
        if await _send(
            bot, row["user_id"],
            f"🏯 {name} 已探索完成，发送 /dungeon 或点击菜单领取结算。"
        ):
            await db.execute(
                "UPDATE dungeon_jobs SET notified_at=? "
                "WHERE user_id=? AND notified_at IS NULL",
                (now, row["user_id"]))
            sent += 1
        else:
            await _record_failure("dungeon_jobs", row["user_id"],
                                  int(row["notify_attempts"] or 0), now)
    return sent


async def _record_failure(table: str, user_id: int, attempts: int, now: int):
    """发送失败：累加重试次数，达上限（5 次）则标记已通知、停止重试。"""
    next_attempts = attempts + 1
    if next_attempts >= MAX_NOTIFY_ATTEMPTS:
        await db.execute(
            f"UPDATE {table} SET notify_attempts=?, notified_at=? "
            "WHERE user_id=? AND notified_at IS NULL",
            (next_attempts, now, user_id))
    else:
        await db.execute(
            f"UPDATE {table} SET notify_attempts=? "
            "WHERE user_id=? AND notified_at IS NULL",
            (next_attempts, user_id))


async def _send(bot, user_id: int, text: str) -> bool:
    try:
        await bot.send_message(user_id, text)
        return True
    except Exception as exc:  # pragma: no cover - depends on Telegram transport
        log.warning("notify user %s failed: %s", user_id, exc)
        return False
