import copy

import pytest
import pytest_asyncio

from config import bosses
from config import realms as R
from models import db
from services import character, daily, pvp, sect, world_boss


@pytest_asyncio.fixture
async def temp_db(tmp_path):
    await db.init_db(str(tmp_path / "m3-test.db"))
    try:
        yield
    finally:
        await db.close_db()


@pytest.mark.asyncio
async def test_pvp_duel_updates_ratings_and_reward(temp_db):
    a, b = 3001, 3002
    await character.create(a, "attacker")
    await character.create(b, "defender")
    await character.set_progress(a, 1, R.num_stages(1) - 1, 0)
    await character.set_progress(b, 1, 0, 0)

    res = await pvp.duel(a, b, now=1000)
    assert res["status"] == "ok"
    rows = await pvp.top()
    assert {row["user_id"] for row in rows} == {a, b}
    assert any(row["rating"] != 1000 for row in rows)
    assert sum(row["reputation"] for row in rows) == pvp.WIN_REPUTATION + pvp.LOSS_REPUTATION
    assert (await character.get(a)).spirit_stone >= 105


@pytest.mark.asyncio
async def test_pvp_duel_shows_real_names(temp_db):
    a, b = 3101, 3102
    await character.create(a, "alice")
    await character.create(b, "bob")
    await character.set_progress(a, 1, R.num_stages(1) - 1, 0)
    await character.set_progress(b, 1, 0, 0)

    res = await pvp.duel(a, b, now=1000)
    assert res["status"] == "ok"
    assert res["attacker_name"] == "alice"
    assert res["defender_name"] == "bob"
    joined = "\n".join(res["log"])
    assert "道友" not in joined and "对手" not in joined
    assert "alice" in joined and "bob" in joined

    # 群昵称（无库内 @username）应作为显示名透传进战斗日志。
    res2 = await pvp.duel(a, b, now=1000, attacker_name="剑无尘")
    assert res2["attacker_name"] == "剑无尘"
    assert "剑无尘" in "\n".join(res2["log"])


@pytest.mark.asyncio
async def test_pvp_duel_falls_back_to_user_ids(temp_db):
    a, b = 3111, 3112
    await character.create(a, "")
    await character.create(b, "")
    await character.set_progress(a, 1, R.num_stages(1) - 1, 0)
    await character.set_progress(b, 1, 0, 0)

    res = await pvp.duel(a, b, now=1000)

    assert res["status"] == "ok"
    assert res["attacker_name"] == str(a)
    assert res["defender_name"] == str(b)
    joined = "\n".join(res["log"])
    assert "道友" not in joined and "对手" not in joined
    assert str(a) in joined and str(b) in joined


@pytest.mark.asyncio
async def test_world_boss_challenge_defeats_and_rewards(temp_db):
    original = copy.deepcopy(bosses.WORLD_BOSSES["ancient_dragon"])
    bosses.WORLD_BOSSES["ancient_dragon"]["hp"] = 1
    bosses.WORLD_BOSSES["ancient_dragon"]["stone_pool"] = 100
    try:
        uid = 3003
        await character.create(uid, "bosskiller")
        await character.set_progress(uid, 3, 0, 0)
        await db.execute(
            "UPDATE characters SET stamina=?, stamina_at=? WHERE user_id=?",
            (200, 1000, uid))

        res = await world_boss.challenge(-100, uid, now=1000)
        assert res["status"] == "ok"
        assert res["defeated"]
        assert (await world_boss.challenge(-100, uid, now=1001))["status"] == "defeated"
        assert await character.item_qty(uid, "妖丹") >= 8
        assert (await character.get(uid)).spirit_stone >= 200
    finally:
        bosses.WORLD_BOSSES["ancient_dragon"] = original


@pytest.mark.asyncio
async def test_sect_create_task_and_redeem(temp_db):
    uid = 3004
    await character.create(uid, "leader")
    await character.set_progress(uid, 1, 0, 0)
    await character.add_stone(uid, 500)

    assert (await sect.create(uid, "青云门", now=1000))["status"] == "ok"
    assert (await sect.task(uid, now=1000))["status"] == "ok"
    assert (await sect.task(uid, now=1001))["status"] == "done"
    await db.execute(
        "UPDATE sect_members SET contribution=? WHERE user_id=?",
        (40, uid))
    res = await sect.redeem(uid, "烈火诀残页")
    assert res["status"] == "ok"
    assert await character.item_qty(uid, "烈火诀残页") == 1


@pytest.mark.asyncio
async def test_daily_checkin_once_per_day(temp_db):
    uid = 3005
    await character.create(uid, "daily")
    first = await daily.checkin(uid, now=1000)
    second = await daily.checkin(uid, now=1001)

    assert first["status"] == "ok"
    assert second["status"] == "done"
    assert first["streak"] == second["streak"] == 1
