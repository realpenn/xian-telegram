"""领域事件入口：任务、成就和社交播报共用。"""
from __future__ import annotations

import logging
import time

from services import quests, social

log = logging.getLogger("xian.game_events")


async def emit_conn(conn, user_id: int, event_type: str,
                    payload: dict | None = None, now: int = None):
    now = int(time.time()) if now is None else now
    payload = payload or {}
    # 事件副作用（任务/成就/群播报）隔离在 savepoint 内：任意异常只回滚事件写入，
    # 绝不连累核心动作（突破、历练奖励等）所在的外层事务。
    await conn.execute("SAVEPOINT game_event")
    try:
        await quests.record_event_conn(conn, user_id, event_type, payload, now)
        await social.queue_from_event_conn(conn, user_id, event_type, payload, now)
    except Exception:
        await conn.execute("ROLLBACK TO game_event")
        log.exception("game event %s for user %s failed; core action preserved",
                      event_type, user_id)
    finally:
        await conn.execute("RELEASE game_event")
