import pytest
import pytest_asyncio

from config import realms as R
from config.dungeons import DUNGEONS
from models import db
from services import character, crafting, dungeon, shop


@pytest_asyncio.fixture
async def temp_db(tmp_path):
    await db.init_db(str(tmp_path / "m2-test.db"))
    try:
        yield
    finally:
        await db.close_db()


@pytest.mark.asyncio
async def test_crafting_collects_stack_item(temp_db):
    uid = 2001
    await character.create(uid, "tester")
    await character.set_progress(uid, 1, 0, 0)
    await character.add_stone(uid, 100)
    await character.add_item(uid, "灵草", 3)

    res = await crafting.start_job(uid, "heal_pill", now=1000)
    assert res["status"] == "started"
    assert await character.item_qty(uid, "疗伤丹") == 0

    collected = await crafting.collect_ready(uid, now=1100)
    assert collected == [{"kind": "item", "name": "疗伤丹", "qty": 1}]
    assert await character.item_qty(uid, "疗伤丹") == 1


@pytest.mark.asyncio
async def test_forge_equipment_can_be_equipped_and_changes_stats(temp_db):
    uid = 2002
    await character.create(uid, "tester")
    await character.set_progress(uid, 1, 0, 0)
    await character.add_stone(uid, 200)
    await character.add_item(uid, "玄铁矿", 5)
    await character.add_item(uid, "兽皮", 2)

    before = await character.stats(await character.get(uid))
    assert (await crafting.start_job(uid, "forge_sword", now=1000))["status"] == "started"
    await crafting.collect_ready(uid, now=1100)
    inst = (await character.item_instances(uid))[0]

    assert (await character.equip_instance(uid, inst["id"]))["status"] == "ok"
    after = await character.stats(await character.get(uid))
    assert after["atk"] > before["atk"]


@pytest.mark.asyncio
async def test_equipment_affixes_apply_percent_stats_and_combat_mods(temp_db):
    uid = 2016
    await character.create(uid, "tester")
    before = await character.stats(await character.get(uid))
    await character.create_item_instance(
        uid, "聚灵佩",
        affixes={"atk_pct": 0.1, "lifesteal_pct": 0.2, "pierce": 9})
    inst = (await character.item_instances(uid))[0]

    assert (await character.equip_instance(uid, inst["id"]))["status"] == "ok"
    after = await character.stats(await character.get(uid))
    mods = await character.combat_mods(uid)

    assert after["atk"] > before["atk"]
    assert mods["lifesteal_pct"] == 0.2
    assert mods["pierce"] == 9


@pytest.mark.asyncio
async def test_two_accessories_can_be_equipped(temp_db):
    uid = 2012
    await character.create(uid, "tester")
    await character.create_item_instance(uid, "聚灵佩")
    await character.create_item_instance(uid, "聚灵佩")

    items = await character.item_instances(uid)
    assert (await character.equip_instance(uid, items[0]["id"]))["slot"] == "accessory:1"
    assert (await character.equip_instance(uid, items[1]["id"]))["slot"] == "accessory:2"

    equipped_slots = {inst["equipped_slot"] for inst in await character.equipped_items(uid)}
    assert {"accessory:1", "accessory:2"} <= equipped_slots


@pytest.mark.asyncio
async def test_legacy_accessory_slot_is_normalized(temp_db):
    uid = 2013
    await character.create(uid, "tester")
    await character.create_item_instance(uid, "聚灵佩")
    await character.create_item_instance(uid, "聚灵佩")
    items = await character.item_instances(uid)
    await db.execute("UPDATE item_instances SET equipped_slot='accessory' WHERE id=?",
                     (items[0]["id"],))

    res = await character.equip_instance(uid, items[1]["id"])
    equipped_slots = {inst["equipped_slot"] for inst in await character.equipped_items(uid)}

    assert res["slot"] == "accessory:2"
    assert {"accessory:1", "accessory:2"} <= equipped_slots


@pytest.mark.asyncio
async def test_shop_buy_and_sell_stack_items(temp_db):
    uid = 2003
    await character.create(uid, "tester")
    bought = await shop.buy(uid, "灵草", qty=2)
    assert bought["status"] == "ok"
    assert await character.item_qty(uid, "灵草") == 2

    sold = await shop.sell(uid, "灵草", qty=1)
    assert sold["status"] == "ok"
    assert await character.item_qty(uid, "灵草") == 1


@pytest.mark.asyncio
async def test_dungeon_daily_limit_and_rewards(temp_db):
    uid = 2004
    await character.create(uid, "tester")
    await character.set_progress(uid, 3, 0, 0)
    await character.add_stone(uid, 2000)  # 秘境入场费（#13）
    await db.execute(
        "UPDATE characters SET stamina=?, stamina_at=? WHERE user_id=?",
        (200, 1000, uid))

    now = 1000
    stamina_left = []
    for _ in range(3):
        started = await dungeon.start(uid, "qingyun", now=now)
        pending = await dungeon.collect(uid, now=started["finish_at"] - 1)
        res = await dungeon.collect(uid, now=started["finish_at"])

        assert started["status"] == "started"
        assert pending["status"] == "pending"
        stamina_left.append(started["stamina_left"])
        assert res["status"] == "ok"
        assert res["cleared"] >= 1
        now = started["finish_at"] + 1

    assert stamina_left[0] == 150
    assert stamina_left[0] > stamina_left[1] > stamina_left[2]
    assert (await dungeon.start(uid, "qingyun", now=now))["status"] == "daily_done"


@pytest.mark.asyncio
async def test_dungeon_requires_single_run_stamina_cost(temp_db):
    uid = 2017
    await character.create(uid, "tester")
    await character.set_progress(uid, 3, 0, 0)
    await db.execute(
        "UPDATE characters SET stamina=?, stamina_at=? WHERE user_id=?",
        (49, 1000, uid))

    res = await dungeon.run(uid, "qingyun", now=1000)

    assert res["status"] == "no_stamina"
    assert res["need"] == 50


def test_dungeons_cover_each_realm_with_daily_stamina_budget():
    realms = {d["realm"] for d in DUNGEONS.values()}
    assert realms == set(range(len(R.REALM_NAMES)))

    for d in DUNGEONS.values():
        realm = d["realm"]
        assert d["stamina"] == R.STAMINA_CAP[realm] // dungeon.DUNGEON_DAILY_LIMIT
        assert d["cult"] > 0
        assert d["stone"][0] > 0


def test_dungeon_strength_scales_by_realm():
    by_realm = sorted(DUNGEONS.values(), key=lambda d: d["realm"])
    boss_hp = [d["boss"]["hp"] for d in by_realm]
    boss_atk = [d["boss"]["atk"] for d in by_realm]
    rewards = [d["cult"] for d in by_realm]

    assert boss_hp == sorted(boss_hp)
    assert boss_atk == sorted(boss_atk)
    assert rewards == sorted(rewards)


@pytest.mark.asyncio
async def test_each_realm_can_start_and_collect_its_dungeon(temp_db):
    for realm, key in enumerate(("lingxi", "xuanming", "qingyun", "tianxu")):
        uid = 2020 + realm
        await character.create(uid, f"tester-{realm}")
        await character.set_progress(uid, realm, 0, 0)
        await character.add_stone(uid, 1000)  # 秘境入场费（#13）
        await db.execute(
            "UPDATE characters SET stamina=?, stamina_at=? WHERE user_id=?",
            (R.STAMINA_CAP[realm], 1000, uid))

        started = await dungeon.start(uid, key, now=1000 + realm)
        pending = await dungeon.collect(uid, now=started["finish_at"] - 1)
        res = await dungeon.collect(uid, now=started["finish_at"])

        assert started["status"] == "started"
        assert started["stamina_left"] == R.STAMINA_CAP[realm] - DUNGEONS[key]["stamina"]
        assert pending["status"] == "pending"
        assert res["status"] == "ok"
        assert res["dungeon_key"] == key
        assert res["cleared"] >= 1
        assert res["layers"] == DUNGEONS[key]["layers"]


@pytest.mark.asyncio
async def test_learn_skill_from_pages(temp_db):
    uid = 2005
    await character.create(uid, "tester")
    await character.add_item(uid, "烈火诀残页", 3)

    res = await character.learn_skill_from_pages(uid, "烈火诀残页")
    assert res["status"] == "ok"
    assert "烈火诀" in await character.get_skills(uid)
    assert await character.item_qty(uid, "烈火诀残页") == 0


@pytest.mark.asyncio
async def test_mind_skill_uses_passive_slot_and_changes_stats(temp_db):
    uid = 2015
    await character.create(uid, "tester")

    assert await character.get_mind_skill(uid) == "吐纳诀"
    assert "吐纳诀" not in await character.get_skills(uid)

    before = await character.stats(await character.get(uid))
    await character.add_item(uid, "归元心法残页", 3)
    res = await character.learn_skill_from_pages(uid, "归元心法残页")
    after = await character.stats(await character.get(uid))

    assert res["status"] == "ok"
    assert await character.get_mind_skill(uid) == "归元心法"
    assert "归元心法" not in await character.get_skills(uid)
    assert after["hp"] > before["hp"]
