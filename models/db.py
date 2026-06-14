"""SQLite 访问层：单连接 + WAL + 写串行化（spec §13/§14）。

约定（供后续模块复用）：
- 读用 ``fetchone`` / ``fetchall``（WAL 下并发读安全，无锁）。
- 写用 ``execute`` / ``executemany``（经 ``_write_lock`` 串行化，护灵石/库存等）。
- schema 启动时幂等建表。
"""
from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

import aiosqlite

_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "xian.db")
_conn = None
_write_lock = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    tg_user_id  INTEGER PRIMARY KEY,
    username    TEXT,
    created_at  INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS characters (
    user_id       INTEGER PRIMARY KEY,
    root_bone     INTEGER NOT NULL,
    spirit_root   TEXT NOT NULL,
    realm         INTEGER NOT NULL DEFAULT 0,
    stage         INTEGER NOT NULL DEFAULT 0,
    cultivation   INTEGER NOT NULL DEFAULT 0,
    stamina       INTEGER NOT NULL,
    stamina_at    INTEGER NOT NULL,
    seclusion_at  INTEGER,
    spirit_stone  INTEGER NOT NULL DEFAULT 0,
    weapon_key    TEXT NOT NULL DEFAULT '新手剑',
    created_at    INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS inventory (
    user_id   INTEGER NOT NULL,
    item_key  TEXT NOT NULL,
    qty       INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, item_key)
);
CREATE TABLE IF NOT EXISTS character_skills (
    user_id    INTEGER NOT NULL,
    skill_key  TEXT NOT NULL,
    slot       INTEGER NOT NULL,
    PRIMARY KEY (user_id, slot)
);
"""


async def init_db(path: str = None):
    global _conn, _write_lock
    db_path = path or _DB_PATH
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    if _conn is not None:
        await _conn.close()
    _conn = await aiosqlite.connect(db_path)
    _conn.row_factory = aiosqlite.Row
    _write_lock = asyncio.Lock()
    await _conn.execute("PRAGMA journal_mode=WAL;")
    await _conn.executescript(SCHEMA)
    await _conn.commit()


async def close_db():
    global _conn, _write_lock
    if _conn is not None:
        await _conn.close()
        _conn = None
    _write_lock = None


def _c():
    assert _conn is not None, "DB 未初始化，请先 await init_db()"
    return _conn


def _lock():
    assert _write_lock is not None, "DB 未初始化，请先 await init_db()"
    return _write_lock


async def fetchone(sql, params=()):
    cur = await _c().execute(sql, params)
    row = await cur.fetchone()
    await cur.close()
    return row


async def fetchall(sql, params=()):
    cur = await _c().execute(sql, params)
    rows = await cur.fetchall()
    await cur.close()
    return rows


async def execute(sql, params=()):
    async with _lock():
        await _c().execute(sql, params)
        await _c().commit()


@asynccontextmanager
async def transaction():
    """串行化写事务；用于检查状态、扣资源、领奖励等原子流程。"""
    async with _lock():
        conn = _c()
        await conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
        except Exception:
            await conn.rollback()
            raise
        else:
            await conn.commit()
