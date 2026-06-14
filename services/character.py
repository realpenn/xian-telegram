"""角色服务：注册/读取/属性计算/储物袋。读取时惰性恢复精力并落库。"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass

from config import realms as R
from config.items import weapon_bonus
from config.skills import STARTER_SKILL
from models import db
from services import settle

SPIRIT_ROOTS = ["天灵根", "金灵根", "木灵根", "水灵根", "火灵根",
                "土灵根", "雷灵根", "冰灵根", "风灵根", "五行杂灵根"]


@dataclass
class Character:
    user_id: int
    root_bone: int
    spirit_root: str
    realm: int
    stage: int
    cultivation: int
    stamina: int
    stamina_at: int
    seclusion_at: int   # 0 表示未闭关
    spirit_stone: int
    weapon_key: str


async def exists(user_id: int) -> bool:
    return await db.fetchone("SELECT 1 FROM characters WHERE user_id=?", (user_id,)) is not None


async def create(user_id: int, username: str) -> Character:
    now = int(time.time())
    root = random.randint(40, 80)
    spirit = random.choice(SPIRIT_ROOTS)
    cap = R.STAMINA_CAP[0]
    await db.execute(
        "INSERT OR IGNORE INTO users(tg_user_id, username, created_at) VALUES(?,?,?)",
        (user_id, username, now))
    # OR IGNORE：并发双 /start 时不抛 IntegrityError，已存在则保留原存档。
    await db.execute(
        "INSERT OR IGNORE INTO characters(user_id, root_bone, spirit_root, realm, stage, "
        "cultivation, stamina, stamina_at, seclusion_at, spirit_stone, weapon_key, created_at) "
        "VALUES(?,?,?,0,0,0,?,?,NULL,100,'新手剑',?)",
        (user_id, root, spirit, cap, now, now))
    await db.execute(
        "INSERT OR IGNORE INTO character_skills(user_id, skill_key, slot) VALUES(?,?,0)",
        (user_id, STARTER_SKILL))
    return await get(user_id)


async def get(user_id: int):
    row = await db.fetchone("SELECT * FROM characters WHERE user_id=?", (user_id,))
    if not row:
        return None
    cap = R.STAMINA_CAP[row["realm"]]
    now = int(time.time())
    new_stam, new_at = settle.regen_stamina(row["stamina"], row["stamina_at"], cap, now)
    if new_stam != row["stamina"] or new_at != row["stamina_at"]:
        await db.execute("UPDATE characters SET stamina=?, stamina_at=? WHERE user_id=?",
                         (new_stam, new_at, user_id))
    return Character(
        user_id=user_id, root_bone=row["root_bone"], spirit_root=row["spirit_root"],
        realm=row["realm"], stage=row["stage"], cultivation=row["cultivation"],
        stamina=new_stam, stamina_at=new_at, seclusion_at=row["seclusion_at"] or 0,
        spirit_stone=row["spirit_stone"], weapon_key=row["weapon_key"])


async def stats(char: Character) -> dict:
    base = R.base_stats(char.realm, char.stage)
    for k, v in weapon_bonus(char.weapon_key).items():
        base[k] = base.get(k, 0) + v
    return base


async def get_skills(user_id: int):
    rows = await db.fetchall(
        "SELECT skill_key FROM character_skills WHERE user_id=? ORDER BY slot", (user_id,))
    return [r["skill_key"] for r in rows]


async def inventory(user_id: int):
    rows = await db.fetchall(
        "SELECT item_key, qty FROM inventory WHERE user_id=? AND qty>0 ORDER BY item_key",
        (user_id,))
    return [(r["item_key"], r["qty"]) for r in rows]


async def item_qty(user_id: int, key: str) -> int:
    row = await db.fetchone(
        "SELECT qty FROM inventory WHERE user_id=? AND item_key=?", (user_id, key))
    return row["qty"] if row else 0


async def add_item(user_id: int, key: str, qty: int):
    await db.execute(
        "INSERT INTO inventory(user_id, item_key, qty) VALUES(?,?,?) "
        "ON CONFLICT(user_id, item_key) DO UPDATE SET qty = MAX(0, qty + ?)",
        (user_id, key, max(0, qty), qty))


async def add_stone(user_id: int, amount: int):
    await db.execute(
        "UPDATE characters SET spirit_stone = MAX(0, spirit_stone + ?) WHERE user_id=?",
        (amount, user_id))


async def spend_stamina(user_id: int, amount: int):
    await db.execute(
        "UPDATE characters SET stamina = MAX(0, stamina - ?) WHERE user_id=?",
        (amount, user_id))


async def set_cultivation(user_id: int, cultivation: int):
    await db.execute("UPDATE characters SET cultivation=? WHERE user_id=?",
                     (max(0, cultivation), user_id))


async def set_progress(user_id: int, realm: int, stage: int, cultivation: int):
    await db.execute(
        "UPDATE characters SET realm=?, stage=?, cultivation=? WHERE user_id=?",
        (realm, stage, max(0, cultivation), user_id))


async def set_seclusion(user_id: int, ts):
    await db.execute("UPDATE characters SET seclusion_at=? WHERE user_id=?", (ts, user_id))
