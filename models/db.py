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
    alchemy_prof  INTEGER NOT NULL DEFAULT 0,
    forge_prof    INTEGER NOT NULL DEFAULT 0,
    debuff_json   TEXT NOT NULL DEFAULT '{}',
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
CREATE TABLE IF NOT EXISTS item_instances (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER NOT NULL,
    base_key       TEXT NOT NULL,
    tier           TEXT NOT NULL,
    affixes_json   TEXT NOT NULL DEFAULT '{}',
    equipped_slot  TEXT
);
CREATE TABLE IF NOT EXISTS recipes_known (
    user_id     INTEGER NOT NULL,
    recipe_key  TEXT NOT NULL,
    PRIMARY KEY (user_id, recipe_key)
);
CREATE TABLE IF NOT EXISTS crafting_jobs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    craft_type  TEXT NOT NULL,
    recipe_key  TEXT NOT NULL,
    start_at    INTEGER NOT NULL,
    finish_at   INTEGER NOT NULL,
    status      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dungeon_runs (
    user_id      INTEGER NOT NULL,
    dungeon_key  TEXT NOT NULL,
    day          TEXT NOT NULL,
    runs         INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, dungeon_key, day)
);
CREATE TABLE IF NOT EXISTS pvp_ratings (
    user_id        INTEGER PRIMARY KEY,
    rating         INTEGER NOT NULL DEFAULT 1000,
    wins           INTEGER NOT NULL DEFAULT 0,
    losses         INTEGER NOT NULL DEFAULT 0,
    daily_count    INTEGER NOT NULL DEFAULT 0,
    daily_reset_at INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS world_boss (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id       INTEGER NOT NULL,
    boss_key      TEXT NOT NULL,
    total_hp      INTEGER NOT NULL,
    remaining_hp  INTEGER NOT NULL,
    spawn_at      INTEGER NOT NULL,
    expire_at     INTEGER NOT NULL,
    status        TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS world_boss_damage (
    boss_id  INTEGER NOT NULL,
    user_id  INTEGER NOT NULL,
    damage   INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (boss_id, user_id)
);
CREATE TABLE IF NOT EXISTS sects (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    name               TEXT NOT NULL UNIQUE,
    level              INTEGER NOT NULL DEFAULT 1,
    contribution_pool  INTEGER NOT NULL DEFAULT 0,
    leader_user_id     INTEGER NOT NULL,
    created_at         INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS sect_members (
    sect_id       INTEGER NOT NULL,
    user_id       INTEGER NOT NULL,
    role          TEXT NOT NULL,
    contribution  INTEGER NOT NULL DEFAULT 0,
    joined_at     INTEGER NOT NULL,
    PRIMARY KEY (user_id)
);
CREATE TABLE IF NOT EXISTS sect_tasks (
    user_id  INTEGER NOT NULL,
    day      TEXT NOT NULL,
    done     INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, day)
);
CREATE TABLE IF NOT EXISTS daily (
    user_id          INTEGER PRIMARY KEY,
    last_checkin_day TEXT,
    streak           INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS bot_chats (
    chat_id       INTEGER PRIMARY KEY,
    title         TEXT,
    last_seen_at  INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS callback_tokens (
    token        TEXT PRIMARY KEY,
    user_id      INTEGER,
    action       TEXT NOT NULL,
    created_at   INTEGER NOT NULL,
    consumed_at  INTEGER
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
    await _ensure_column(_conn, "characters", "alchemy_prof", "INTEGER NOT NULL DEFAULT 0")
    await _ensure_column(_conn, "characters", "forge_prof", "INTEGER NOT NULL DEFAULT 0")
    await _ensure_column(_conn, "characters", "debuff_json", "TEXT NOT NULL DEFAULT '{}'")
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


async def _ensure_column(conn, table: str, column: str, definition: str):
    cur = await conn.execute(f"PRAGMA table_info({table})")
    columns = {row[1] for row in await cur.fetchall()}
    await cur.close()
    if column not in columns:
        await conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


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
