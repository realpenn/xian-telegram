import pytest
import pytest_asyncio

from config import realms as R
from models import db
from services import character, settle


@pytest_asyncio.fixture
async def temp_db(tmp_path):
    await db.init_db(str(tmp_path / "daohang.db"))
    try:
        yield
    finally:
        await db.close_db()


def test_overflow_to_daohang_full_huashen():
    cost = R.advance_cost(4, 3)
    kept, daohang = settle.overflow_to_daohang(4, 3, cost, 1000)

    assert kept == cost
    assert daohang == 300


def test_overflow_to_daohang_yuanying_cap_transition():
    cost = R.advance_cost(3, 3)
    kept, daohang = settle.overflow_to_daohang(3, 3, cost, 1000)

    assert kept == cost
    assert daohang == 150


def test_overflow_to_daohang_other_progress_is_unchanged():
    kept, daohang = settle.overflow_to_daohang(3, 2, 100, 1000)

    assert kept == 1100
    assert daohang == 0


@pytest.mark.asyncio
async def test_collect_seclusion_converts_huashen_cap_overflow(temp_db):
    uid = 9401
    cost = R.advance_cost(4, 3)
    await character.create(uid, "cap")
    await character.set_progress(uid, 4, 3, cost)
    await db.execute("UPDATE characters SET root_bone=0 WHERE user_id=?", (uid,))

    await character.start_seclusion(uid, now=1000)
    res = await character.collect_seclusion(uid, now=1000 + 3600)
    row = await db.fetchone("SELECT cultivation, daohang FROM characters WHERE user_id=?", (uid,))
    event = await db.fetchone(
        "SELECT event_type, amount FROM path_events WHERE user_id=? AND event_type='overflow'",
        (uid,))

    assert res["status"] == "collected"
    assert res["cultivation"] == cost
    assert res["daohang"] > 0
    assert row["cultivation"] == cost
    assert row["daohang"] == res["daohang"]
    assert event["amount"] == res["daohang"]


@pytest.mark.asyncio
async def test_touch_activity_auto_collect_converts_overflow(temp_db):
    uid = 9402
    cost = R.advance_cost(4, 3)
    await character.create(uid, "auto")
    await character.set_progress(uid, 4, 3, cost)
    await db.execute("UPDATE characters SET root_bone=0 WHERE user_id=?", (uid,))
    await db.execute("UPDATE users SET last_seen_at=? WHERE tg_user_id=?", (1000, uid))

    res = await character.touch_activity(uid, "auto", now=1000 + 7200)
    row = await db.fetchone("SELECT cultivation, daohang FROM characters WHERE user_id=?", (uid,))

    assert res["status"] == "ok"
    assert res["auto_cultivation"] > 0
    assert row["cultivation"] == cost
    assert row["daohang"] > 0
