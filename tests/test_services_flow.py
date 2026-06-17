import asyncio
import time

import pytest
import pytest_asyncio

from config import realms as R
from config.maps import MAPS
from models import db
from services import breakthrough, character, cultivation
from services import dungeon as dungeon_service
from services import explore as explore_service


@pytest_asyncio.fixture
async def temp_db(tmp_path):
    await db.init_db(str(tmp_path / "xian-test.db"))
    try:
        yield
    finally:
        await db.close_db()


@pytest.mark.asyncio
async def test_db_write_lock_waits_in_running_loop(temp_db):
    async with db.transaction():
        waiter = asyncio.create_task(
            db.execute(
                "INSERT OR IGNORE INTO users(tg_user_id, username, created_at) VALUES(?,?,?)",
                (9001, "waiter", 0)))
        await asyncio.sleep(0.01)
        assert not waiter.done()

    await waiter
    row = await db.fetchone("SELECT username FROM users WHERE tg_user_id=?", (9001,))
    assert row["username"] == "waiter"


@pytest.mark.asyncio
async def test_explore_blocked_during_dungeon(temp_db):
    uid = 1101
    await character.create(uid, "tester")
    started = await dungeon_service.start(uid, "lingxi")
    assert started["status"] == "started"

    res = await explore_service.start(uid, "后山")

    assert res["status"] == "busy_dungeon"
    assert await explore_service.active_run(uid) is None
    assert await dungeon_service.active_run(uid) is not None


@pytest.mark.asyncio
async def test_dungeon_blocked_during_explore(temp_db):
    uid = 1102
    await character.create(uid, "tester")
    started = await explore_service.start(uid, "后山")
    assert started["status"] == "started"

    res = await dungeon_service.start(uid, "lingxi")

    assert res["status"] == "busy_explore"
    assert await dungeon_service.active_run(uid) is None
    assert await explore_service.active_run(uid) is not None


@pytest.mark.asyncio
async def test_seclusion_can_run_during_timed_activity(temp_db):
    uid = 1103
    await character.create(uid, "tester")
    started = await explore_service.start(uid, "后山")
    assert started["status"] == "started"

    res = await cultivation.start(uid)

    assert res["status"] == "started"
    assert (await character.get(uid)).seclusion_at
    assert await explore_service.active_run(uid) is not None


@pytest.mark.asyncio
async def test_explore_can_run_during_seclusion(temp_db):
    uid = 1001
    await character.create(uid, "tester")
    await cultivation.start(uid)
    before = await character.get(uid)

    res = await explore_service.start(uid, "后山")
    after = await character.get(uid)

    assert res["status"] == "started"
    assert after.stamina == before.stamina - 10
    assert after.seclusion_at


@pytest.mark.asyncio
async def test_concurrent_explore_spends_stamina_once(temp_db):
    uid = 1002
    await character.create(uid, "tester")
    now = int(time.time())
    await db.execute(
        "UPDATE characters SET stamina=?, stamina_at=? WHERE user_id=?",
        (10, now, uid))

    results = await asyncio.gather(
        explore_service.start(uid, "后山"),
        explore_service.start(uid, "后山"))
    statuses = sorted(r["status"] for r in results)
    after = await character.get(uid)

    assert statuses == ["pending", "started"]
    assert after.stamina == 0


def test_big_breakthrough_pills_drop_before_target_realm():
    for target_realm, rule in R.BIG_BREAKTHROUGH.items():
        pill = rule["pill"]
        assert any(
            m["realm"] < target_realm and any(drop[0] == pill for drop in m["drops"])
            for m in MAPS.values()
        ), f"{pill} must drop before realm {target_realm}"


@pytest.mark.asyncio
async def test_concurrent_big_breakthrough_succeeds_once(temp_db, monkeypatch):
    uid = 1003
    await character.create(uid, "tester")
    last_qi = R.num_stages(0) - 1
    cost = R.advance_cost(0, last_qi)
    await character.set_progress(uid, 0, last_qi, cost)
    await character.add_item(uid, "筑基丹", 1)
    monkeypatch.setattr(breakthrough.random, "random", lambda: 0.0)

    results = await asyncio.gather(
        breakthrough.try_advance(uid),
        breakthrough.try_advance(uid))
    statuses = [r["status"] for r in results]
    char = await character.get(uid)
    pill_qty = await character.item_qty(uid, "筑基丹")

    assert statuses.count("big_success") == 1
    assert char.realm == 1
    assert char.stage == 0
    assert pill_qty == 0
