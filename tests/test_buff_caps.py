import json

import pytest
import pytest_asyncio

from config import buffs as BUFFS
from config import realms as R
from models import db
from services import character, items, settle


@pytest_asyncio.fixture
async def temp_db(tmp_path):
    await db.init_db(str(tmp_path / "buff-caps.db"))
    try:
        yield
    finally:
        await db.close_db()


@pytest.mark.asyncio
async def test_attack_percent_buffs_are_clamped(temp_db):
    uid = 9201
    await character.create(uid, "atkcap")
    await character.create_item_instance(uid, "玄铁剑", affixes={"atk_pct": 0.20})
    inst = (await character.item_instances(uid))[0]
    await character.equip_instance(uid, inst["id"])
    await character.add_item(uid, "虎力丹", 1)
    await items.use(uid, "虎力丹")

    st = await character.stats(await character.get_at(uid, now=1000))
    raw = R.base_stats(0, 0)["atk"] + 38

    assert st["atk"] == int(raw * (1 + BUFFS.ATTACK_PCT_CAP))


@pytest.mark.asyncio
async def test_survival_percent_buffs_are_clamped(temp_db):
    uid = 9202
    await character.create(uid, "hpcap")
    await character.create_item_instance(uid, "聚灵佩", affixes={"hp_pct": 0.20})
    inst = (await character.item_instances(uid))[0]
    await character.equip_instance(uid, inst["id"])
    state = {"buffs": {"test": {"until": 9_999_999_999, "effects": {"hp_pct": 0.20}}}}
    await db.execute(
        "UPDATE characters SET debuff_json=? WHERE user_id=?",
        (json.dumps(state, ensure_ascii=False), uid))

    st = await character.stats(await character.get_at(uid, now=1000))
    raw = R.base_stats(0, 0)["hp"]

    assert st["hp"] == int(raw * (1 + BUFFS.SURVIVAL_PCT_CAP))


@pytest.mark.asyncio
async def test_pvp_stats_halve_percent_buffs(temp_db):
    uid = 9203
    await character.create(uid, "pvpcap")
    await character.add_item(uid, "虎力丹", 1)
    await items.use(uid, "虎力丹")
    char = await character.get_at(uid, now=1000)

    normal = await character.stats(char)
    pvp = await character.stats(char, pvp=True)
    raw = R.base_stats(0, 0)["atk"] + 5

    assert normal["atk"] == int(raw * 1.10)
    assert pvp["atk"] == int(raw * 1.05)


@pytest.mark.asyncio
async def test_seclusion_percent_buffs_are_clamped(temp_db):
    uid = 9204
    await character.create(uid, "seclusioncap")
    await db.execute("UPDATE characters SET root_bone=0 WHERE user_id=?", (uid,))
    state = {"buffs": {"test": {"until": 9_999_999_999, "effects": {"seclusion_pct": 1.0}}}}
    await db.execute(
        "UPDATE characters SET debuff_json=? WHERE user_id=?",
        (json.dumps(state, ensure_ascii=False), uid))

    await character.start_seclusion(uid, now=1000)
    res = await character.collect_seclusion(uid, now=4600)
    base = settle.seclusion_gain(0, 0, 1000, 4600, root_bone=0)

    assert res["gained"] == settle.seclusion_gain(
        0, 0, 1000, 4600, root_bone=0, place_factor=1 + BUFFS.SECLUSION_PCT_CAP)
