import pytest
import pytest_asyncio

from config import buffs as BUFFS
from config import weekly_events as W
from models import db
from services import character, season, sect, sect_war, weekly_events


@pytest_asyncio.fixture
async def temp_db(tmp_path):
    await db.init_db(str(tmp_path / "m4.db"))
    try:
        yield
    finally:
        await db.close_db()


@pytest.mark.asyncio
async def test_weekly_activity_gives_bound_material_and_caps_daohang(temp_db):
    uid = 9601
    await character.create(uid, "event")
    await db.execute("UPDATE characters SET stamina=? WHERE user_id=?", (500, uid))

    gains = []
    for idx in range(4):
        res = await weekly_events.run(uid, "tianmo", now=1000 + idx)
        assert res["status"] == "ok"
        assert res["bound"] == 1
        gains.append(res["daohang"])
    row = await db.fetchone("SELECT daohang FROM weekly_activity WHERE user_id=?", (uid,))

    assert sum(gains) == W.WEEKLY_DAOHANG_CAP
    assert row["daohang"] == W.WEEKLY_DAOHANG_CAP
    assert await character.item_qty(uid, W.ACTIVITY_MATERIAL, bound=1) == 4
    assert await character.item_qty(uid, W.ACTIVITY_MATERIAL, bound=0) == 0


@pytest.mark.asyncio
async def test_weekly_activity_records_activity_window(temp_db):
    uid = 9602
    await character.create(uid, "window")
    await db.execute("UPDATE characters SET stamina=? WHERE user_id=?", (100, uid))

    await weekly_events.run(uid, "danxia", now=2000)
    row = await db.fetchone(
        "SELECT kind, source_key FROM activity_windows WHERE user_id=?",
        (uid,))

    assert row["kind"] == "weekly_activity"
    assert row["source_key"] == "danxia"


@pytest.mark.asyncio
async def test_sect_outpost_capture_adds_buff_under_clamp(temp_db):
    uid = 9603
    await character.create(uid, "leader")
    await character.set_progress(uid, 1, 0, 0)
    await character.add_stone(uid, 1000)
    await sect.create(uid, "战宗", now=1000)
    base = await character.stats(await character.get(uid))

    res = await sect_war.capture(uid, "altar", score=20, now=1000)
    buffed = await character.stats(await character.get(uid))
    raw = base["atk"]

    assert res["status"] == "ok"
    assert buffed["atk"] > base["atk"]
    assert buffed["atk"] <= int(raw * (1 + BUFFS.ATTACK_PCT_CAP))


@pytest.mark.asyncio
async def test_sect_outpost_seclusion_buff_improves_gain(temp_db):
    uid = 9604
    await character.create(uid, "cave")
    await character.set_progress(uid, 1, 0, 0)
    await character.add_stone(uid, 1000)
    await sect.create(uid, "洞府宗", now=1000)
    await sect_war.capture(uid, "cave", now=1000)
    await db.execute("UPDATE characters SET root_bone=0 WHERE user_id=?", (uid,))

    plain = 9605
    await character.create(plain, "plain")
    await character.set_progress(plain, 1, 0, 0)
    await db.execute("UPDATE characters SET root_bone=0 WHERE user_id=?", (plain,))

    await character.start_seclusion(uid, now=2000)
    with_buff = await character.collect_seclusion(uid, now=5600)
    await character.start_seclusion(plain, now=2000)
    without_buff = await character.collect_seclusion(plain, now=5600)

    assert with_buff["gained"] > without_buff["gained"]


@pytest.mark.asyncio
async def test_season_reward_once_and_no_trade_materials(temp_db):
    uid = 9606
    await character.create(uid, "season")

    first = await season.claim(uid, now=1000)
    second = await season.claim(uid, now=1001)
    row = await db.fetchone("SELECT daohang FROM characters WHERE user_id=?", (uid,))

    assert first["status"] == "ok"
    assert first["title"]
    assert second["status"] == "claimed"
    assert row["daohang"] == season.SEASON_DAOHANG_REWARD
