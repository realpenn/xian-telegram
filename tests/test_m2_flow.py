import pytest
import pytest_asyncio

from config import realms as R
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
    await db.execute(
        "UPDATE characters SET stamina=?, stamina_at=? WHERE user_id=?",
        (200, 1000, uid))

    res = await dungeon.run(uid, "qingyun", now=1000)
    assert res["status"] == "ok"
    assert res["cleared"] >= 1
    assert (await dungeon.run(uid, "qingyun", now=1001))["status"] == "daily_done"


@pytest.mark.asyncio
async def test_learn_skill_from_pages(temp_db):
    uid = 2005
    await character.create(uid, "tester")
    await character.add_item(uid, "烈火诀残页", 3)

    res = await character.learn_skill_from_pages(uid, "烈火诀残页")
    assert res["status"] == "ok"
    assert "烈火诀" in await character.get_skills(uid)
    assert await character.item_qty(uid, "烈火诀残页") == 0
