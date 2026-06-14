"""角色服务：注册/读取/属性计算/储物袋。读取时惰性恢复精力并落库。"""
from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass

from config import realms as R
from config.items import ITEMS, equipment_slot, item_name, weapon_bonus
from config.sects import welfare as sect_welfare_config
from config.skills import (COMBAT_SLOTS, MIND_SLOT, SKILLS, STARTER_MIND, STARTER_SKILL,
                           is_mind_skill, skill_bonus)
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
    debuff_json: dict


async def _select_character(conn, user_id: int):
    cur = await conn.execute("SELECT * FROM characters WHERE user_id=?", (user_id,))
    row = await cur.fetchone()
    await cur.close()
    return row


async def _sect_welfare(conn, user_id: int) -> dict:
    cur = await conn.execute(
        "SELECT s.level FROM sect_members m JOIN sects s ON s.id=m.sect_id WHERE m.user_id=?",
        (user_id,))
    row = await cur.fetchone()
    await cur.close()
    return sect_welfare_config(row["level"]) if row else sect_welfare_config(0)


async def sect_welfare(user_id: int) -> dict:
    row = await db.fetchone(
        "SELECT s.level FROM sect_members m JOIN sects s ON s.id=m.sect_id WHERE m.user_id=?",
        (user_id,))
    return sect_welfare_config(row["level"]) if row else sect_welfare_config(0)


def _settled_stamina(row, now: int = None, welfare: dict = None):
    now = int(time.time()) if now is None else now
    welfare = welfare or sect_welfare_config(0)
    cap = R.STAMINA_CAP[row["realm"]] + welfare["stamina_bonus"]
    return settle.regen_stamina(row["stamina"], row["stamina_at"], cap, now)


def _from_row(row, stamina: int = None, stamina_at: int = None) -> Character:
    return Character(
        user_id=row["user_id"], root_bone=row["root_bone"], spirit_root=row["spirit_root"],
        realm=row["realm"], stage=row["stage"], cultivation=row["cultivation"],
        stamina=row["stamina"] if stamina is None else stamina,
        stamina_at=row["stamina_at"] if stamina_at is None else stamina_at,
        seclusion_at=row["seclusion_at"] or 0,
        spirit_stone=row["spirit_stone"], weapon_key=row["weapon_key"],
        debuff_json=json.loads(row["debuff_json"] or "{}"))


async def exists(user_id: int) -> bool:
    return await db.fetchone("SELECT 1 FROM characters WHERE user_id=?", (user_id,)) is not None


async def create(user_id: int, username: str) -> Character:
    now = int(time.time())
    root = random.randint(40, 80)
    spirit = random.choice(SPIRIT_ROOTS)
    cap = R.STAMINA_CAP[0]
    async with db.transaction() as conn:
        await conn.execute(
            "INSERT OR IGNORE INTO users(tg_user_id, username, created_at) VALUES(?,?,?)",
            (user_id, username, now))
        # OR IGNORE：并发双 /start 时不抛 IntegrityError，已存在则保留原存档。
        await conn.execute(
            "INSERT OR IGNORE INTO characters(user_id, root_bone, spirit_root, realm, stage, "
            "cultivation, stamina, stamina_at, seclusion_at, spirit_stone, weapon_key, created_at) "
            "VALUES(?,?,?,0,0,0,?,?,NULL,100,'新手剑',?)",
            (user_id, root, spirit, cap, now, now))
        await conn.execute(
            "INSERT OR IGNORE INTO character_skills(user_id, skill_key, slot) VALUES(?,?,0)",
            (user_id, STARTER_SKILL))
        await conn.execute(
            "INSERT OR IGNORE INTO character_skills(user_id, skill_key, slot) VALUES(?,?,?)",
            (user_id, STARTER_MIND, MIND_SLOT))
    return await get(user_id)


async def get(user_id: int):
    row = await db.fetchone("SELECT * FROM characters WHERE user_id=?", (user_id,))
    if not row:
        return None
    now = int(time.time())
    welfare = await sect_welfare(user_id)
    cap = R.STAMINA_CAP[row["realm"]] + welfare["stamina_bonus"]
    new_stam, new_at = settle.regen_stamina(row["stamina"], row["stamina_at"], cap, now)
    if new_stam != row["stamina"] or new_at != row["stamina_at"]:
        await db.execute("UPDATE characters SET stamina=?, stamina_at=? WHERE user_id=?",
                         (new_stam, new_at, user_id))
    return _from_row(row, new_stam, new_at)


async def stats(char: Character) -> dict:
    base = R.base_stats(char.realm, char.stage)
    equipped = await equipped_items(char.user_id)
    if equipped:
        for inst in equipped:
            for k, v in equipment_bonus(inst).items():
                base[k] = base.get(k, 0) + v
    else:
        for k, v in weapon_bonus(char.weapon_key).items():
            base[k] = base.get(k, 0) + v
    mind = await get_mind_skill(char.user_id)
    if mind:
        for key, val in skill_bonus(mind).items():
            if key.endswith("_pct"):
                stat_key = key[:-4]
                base[stat_key] = int(base.get(stat_key, 0) * (1 + val))
            else:
                base[key] = base.get(key, 0) + val
    welfare = await sect_welfare(char.user_id)
    if welfare["stat_pct"]:
        for key in R.STAT_KEYS:
            base[key] = int(base[key] * (1 + welfare["stat_pct"]))
    unstable_until = int(char.debuff_json.get("unstable_until", 0))
    if unstable_until > int(time.time()):
        for key in R.STAT_KEYS:
            base[key] = max(1, int(base[key] * 0.9))
    return base


def equipment_bonus(inst: dict) -> dict:
    item = ITEMS.get(inst["base_key"], {})
    bonus = dict(item.get("bonus", {}))
    affixes = inst.get("affixes") or {}
    for key, val in affixes.items():
        bonus[key] = bonus.get(key, 0) + val
    return bonus


async def get_skills(user_id: int):
    rows = await db.fetchall(
        "SELECT skill_key FROM character_skills WHERE user_id=? AND slot>=0 ORDER BY slot",
        (user_id,))
    return [r["skill_key"] for r in rows]


async def get_mind_skill(user_id: int):
    row = await db.fetchone(
        "SELECT skill_key FROM character_skills WHERE user_id=? AND slot=?",
        (user_id, MIND_SLOT))
    return row["skill_key"] if row else None


async def knows_skill(user_id: int, skill_key: str) -> bool:
    row = await db.fetchone(
        "SELECT 1 FROM character_skills WHERE user_id=? AND skill_key=?",
        (user_id, skill_key))
    return row is not None


async def inventory(user_id: int):
    rows = await db.fetchall(
        "SELECT item_key, qty FROM inventory WHERE user_id=? AND qty>0 ORDER BY item_key",
        (user_id,))
    return [(r["item_key"], r["qty"]) for r in rows]


async def item_instances(user_id: int):
    rows = await db.fetchall(
        "SELECT * FROM item_instances WHERE user_id=? ORDER BY equipped_slot DESC, id",
        (user_id,))
    return [_instance_from_row(row) for row in rows]


async def equipped_items(user_id: int):
    rows = await db.fetchall(
        "SELECT * FROM item_instances WHERE user_id=? AND equipped_slot IS NOT NULL ORDER BY id",
        (user_id,))
    return [_instance_from_row(row) for row in rows]


def _instance_from_row(row) -> dict:
    return {
        "id": row["id"], "user_id": row["user_id"], "base_key": row["base_key"],
        "tier": row["tier"], "equipped_slot": row["equipped_slot"],
        "affixes": json.loads(row["affixes_json"] or "{}"),
    }


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


async def spend_stone(user_id: int, amount: int) -> bool:
    async with db.transaction() as conn:
        row = await _select_character(conn, user_id)
        if not row or row["spirit_stone"] < amount:
            return False
        await conn.execute(
            "UPDATE characters SET spirit_stone = spirit_stone - ? WHERE user_id=?",
            (amount, user_id))
        return True


async def spend_stamina(user_id: int, amount: int):
    await db.execute(
        "UPDATE characters SET stamina = MAX(0, stamina - ?) WHERE user_id=?",
        (amount, user_id))


async def reserve_stamina_for_action(user_id: int, amount: int) -> dict:
    async with db.transaction() as conn:
        row = await _select_character(conn, user_id)
        if not row:
            return {"status": "missing"}
        now = int(time.time())
        welfare = await _sect_welfare(conn, user_id)
        stamina, stamina_at = _settled_stamina(row, now, welfare)
        if row["seclusion_at"]:
            if stamina != row["stamina"] or stamina_at != row["stamina_at"]:
                await conn.execute(
                    "UPDATE characters SET stamina=?, stamina_at=? WHERE user_id=?",
                    (stamina, stamina_at, user_id))
            return {"status": "in_seclusion"}
        if stamina < amount:
            if stamina != row["stamina"] or stamina_at != row["stamina_at"]:
                await conn.execute(
                    "UPDATE characters SET stamina=?, stamina_at=? WHERE user_id=?",
                    (stamina, stamina_at, user_id))
            return {"status": "no_stamina", "need": amount, "have": stamina}
        left = stamina - amount
        await conn.execute(
            "UPDATE characters SET stamina=?, stamina_at=? WHERE user_id=?",
            (left, stamina_at, user_id))
        return {"status": "ok", "char": _from_row(row, left, stamina_at), "stamina_left": left}


async def set_cultivation(user_id: int, cultivation: int):
    await db.execute("UPDATE characters SET cultivation=? WHERE user_id=?",
                     (max(0, cultivation), user_id))


async def add_cultivation(user_id: int, amount: int):
    await db.execute(
        "UPDATE characters SET cultivation = MAX(0, cultivation + ?) WHERE user_id=?",
        (amount, user_id))


async def create_item_instance(user_id: int, base_key: str, tier: str = None, affixes=None):
    item = ITEMS[base_key]
    tier = tier or item.get("tier", "凡")
    affixes_json = json.dumps(affixes or {}, ensure_ascii=False)
    await db.execute(
        "INSERT INTO item_instances(user_id, base_key, tier, affixes_json) VALUES(?,?,?,?)",
        (user_id, base_key, tier, affixes_json))


async def equip_instance(user_id: int, instance_id: int) -> dict:
    async with db.transaction() as conn:
        await _normalize_accessory_slots(conn, user_id)
        cur = await conn.execute(
            "SELECT * FROM item_instances WHERE id=? AND user_id=?", (instance_id, user_id))
        inst = await cur.fetchone()
        await cur.close()
        if not inst:
            return {"status": "not_found"}
        slot = equipment_slot(inst["base_key"])
        if not slot:
            return {"status": "not_equipment"}
        target_slot = slot
        if slot == "accessory":
            cur = await conn.execute(
                "SELECT equipped_slot FROM item_instances "
                "WHERE user_id=? AND equipped_slot IN ('accessory:1','accessory:2')",
                (user_id,))
            used = {row["equipped_slot"] for row in await cur.fetchall()}
            await cur.close()
            target_slot = next((s for s in ("accessory:1", "accessory:2") if s not in used),
                               "accessory:1")
        await conn.execute(
            "UPDATE item_instances SET equipped_slot=NULL WHERE user_id=? AND equipped_slot=?",
            (user_id, target_slot))
        await conn.execute(
            "UPDATE item_instances SET equipped_slot=? WHERE id=? AND user_id=?",
            (target_slot, instance_id, user_id))
        return {"status": "ok", "slot": target_slot, "name": item_name(inst["base_key"])}


async def _normalize_accessory_slots(conn, user_id: int):
    cur = await conn.execute(
        "SELECT id, equipped_slot FROM item_instances "
        "WHERE user_id=? AND equipped_slot IN ('accessory','accessory:1','accessory:2') "
        "ORDER BY id",
        (user_id,))
    rows = await cur.fetchall()
    await cur.close()
    used = set()
    updates = []
    for row in rows:
        current = row["equipped_slot"]
        if current in ("accessory:1", "accessory:2") and current not in used:
            target = current
        else:
            target = next((slot for slot in ("accessory:1", "accessory:2")
                           if slot not in used), None)
        if target:
            used.add(target)
        if target != current:
            updates.append((target, row["id"]))
    for target, item_id in updates:
        await conn.execute("UPDATE item_instances SET equipped_slot=? WHERE id=?", (target, item_id))


async def learn_skill_from_pages(user_id: int, page_key: str) -> dict:
    item = ITEMS.get(page_key, {})
    skill_key = item.get("skill")
    need = int(item.get("need", 0))
    if skill_key not in SKILLS:
        return {"status": "bad_page"}
    async with db.transaction() as conn:
        cur = await conn.execute(
            "SELECT qty FROM inventory WHERE user_id=? AND item_key=?", (user_id, page_key))
        inv = await cur.fetchone()
        await cur.close()
        if not inv or inv["qty"] < need:
            return {"status": "need_pages", "need": need, "have": inv["qty"] if inv else 0}
        if is_mind_skill(skill_key):
            slot = MIND_SLOT
            cur = await conn.execute(
                "SELECT skill_key FROM character_skills WHERE user_id=? AND slot=?",
                (user_id, MIND_SLOT))
            current = await cur.fetchone()
            await cur.close()
            if current and current["skill_key"] == skill_key:
                return {"status": "known", "skill": skill_key}
            await conn.execute(
                "UPDATE character_skills SET skill_key=? WHERE user_id=? AND slot=?",
                (skill_key, user_id, MIND_SLOT))
            if not current:
                await conn.execute(
                    "INSERT OR IGNORE INTO character_skills(user_id, skill_key, slot) "
                    "VALUES(?,?,?)",
                    (user_id, skill_key, MIND_SLOT))
        else:
            cur = await conn.execute(
                "SELECT 1 FROM character_skills WHERE user_id=? AND skill_key=?",
                (user_id, skill_key))
            exists = await cur.fetchone()
            await cur.close()
            if exists:
                return {"status": "known", "skill": skill_key}
            cur = await conn.execute(
                "SELECT slot FROM character_skills WHERE user_id=? AND slot>=0 ORDER BY slot",
                (user_id,))
            used = {row["slot"] for row in await cur.fetchall()}
            await cur.close()
            slot = next((i for i in COMBAT_SLOTS if i not in used), 2)
            if slot in used:
                await conn.execute(
                    "UPDATE character_skills SET skill_key=? WHERE user_id=? AND slot=?",
                    (skill_key, user_id, slot))
            else:
                await conn.execute(
                    "INSERT INTO character_skills(user_id, skill_key, slot) VALUES(?,?,?)",
                    (user_id, skill_key, slot))
        await conn.execute(
            "UPDATE inventory SET qty = MAX(0, qty - ?) WHERE user_id=? AND item_key=?",
            (need, user_id, page_key))
        return {"status": "ok", "skill": skill_key, "slot": slot}


async def add_prof(user_id: int, craft_type: str, amount: int):
    column = "alchemy_prof" if craft_type == "alchemy" else "forge_prof"
    await db.execute(
        f"UPDATE characters SET {column} = {column} + ? WHERE user_id=?",
        (amount, user_id))


async def set_progress(user_id: int, realm: int, stage: int, cultivation: int):
    await db.execute(
        "UPDATE characters SET realm=?, stage=?, cultivation=? WHERE user_id=?",
        (realm, stage, max(0, cultivation), user_id))


async def set_seclusion(user_id: int, ts):
    await db.execute("UPDATE characters SET seclusion_at=? WHERE user_id=?", (ts, user_id))


async def start_seclusion(user_id: int, now: int = None) -> dict:
    now = int(time.time()) if now is None else now
    async with db.transaction() as conn:
        row = await _select_character(conn, user_id)
        if not row:
            return {"status": "missing"}
        if row["seclusion_at"]:
            return {"status": "already"}
        welfare = await _sect_welfare(conn, user_id)
        stamina, stamina_at = _settled_stamina(row, now, welfare)
        await conn.execute(
            "UPDATE characters SET stamina=?, stamina_at=?, seclusion_at=? WHERE user_id=?",
            (stamina, stamina_at, now, user_id))
        return {"status": "started"}


async def collect_seclusion(user_id: int, now: int = None) -> dict:
    now = int(time.time()) if now is None else now
    async with db.transaction() as conn:
        row = await _select_character(conn, user_id)
        if not row:
            return {"status": "missing"}
        if not row["seclusion_at"]:
            return {"status": "not_in"}
        welfare = await _sect_welfare(conn, user_id)
        stamina, stamina_at = _settled_stamina(row, now, welfare)
        gained = settle.seclusion_gain(
            row["realm"], row["seclusion_at"], now, row["root_bone"],
            place_factor=1 + welfare["seclusion_pct"],
            offline_cap_hours=settle.OFFLINE_CAP_HOURS + welfare["offline_extra_hours"])
        new_cult = row["cultivation"] + gained
        await conn.execute(
            "UPDATE characters SET cultivation=?, stamina=?, stamina_at=?, seclusion_at=NULL "
            "WHERE user_id=?",
            (new_cult, stamina, stamina_at, user_id))
        cost = R.advance_cost(row["realm"], row["stage"])
        return {"status": "collected", "gained": gained, "cultivation": new_cult,
                "cost": cost, "can_advance": new_cult >= cost,
                "minutes": max(0, (now - row["seclusion_at"]) // 60)}


async def grant_reward(user_id: int, stone: int = 0, cultivation: int = 0, drops: dict = None):
    drops = drops or {}
    async with db.transaction() as conn:
        await conn.execute(
            "UPDATE characters SET spirit_stone = MAX(0, spirit_stone + ?), "
            "cultivation = MAX(0, cultivation + ?) WHERE user_id=?",
            (stone, cultivation, user_id))
        for key, qty in drops.items():
            if qty <= 0:
                continue
            await conn.execute(
                "INSERT INTO inventory(user_id, item_key, qty) VALUES(?,?,?) "
                "ON CONFLICT(user_id, item_key) DO UPDATE SET qty = MAX(0, qty + ?)",
                (user_id, key, qty, qty))
