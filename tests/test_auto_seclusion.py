"""自动闭关改为"返回即自动收功"的回归测试。"""
import pytest
import pytest_asyncio

from models import db
from services import activity, character, settle


@pytest_asyncio.fixture
async def temp_db(tmp_path):
    await db.init_db(str(tmp_path / "auto-seclusion.db"))
    try:
        yield
    finally:
        await db.close_db()


@pytest.mark.asyncio
async def test_touch_activity_auto_collects_and_does_not_trap(temp_db):
    uid = 7001
    await character.create(uid, "idler")
    await db.execute("UPDATE users SET last_seen_at=? WHERE tg_user_id=?", (1000, uid))
    await db.execute("UPDATE characters SET cultivation=0 WHERE user_id=?", (uid,))

    now = 1000 + 5 * 3600  # 闲置约 5 小时后回归
    res = await character.touch_activity(uid, "idler", now=now)

    assert res["status"] == "ok"
    assert res["auto_cultivation"] > 0           # 闲置时段直接结算成修为
    char = await character.get_at(uid, now=now)
    assert char.cultivation > 0
    assert not char.seclusion_at                  # 关键：没有被留在闭关里


@pytest.mark.asyncio
async def test_touch_activity_discounts_when_timed_job_active(temp_db):
    uid = 7002
    await character.create(uid, "explorer")
    await db.execute("UPDATE users SET last_seen_at=? WHERE tg_user_id=?", (1000, uid))
    await db.execute("UPDATE characters SET cultivation=0 WHERE user_id=?", (uid,))
    # 有前台历练窗口 —— 自动闭关仍结算，但重叠时段按双轨折算。
    await db.execute(
        "INSERT INTO explore_runs(user_id, map_key, start_at, finish_at, seed, status) "
        "VALUES(?,?,?,?,?,'active')",
        (uid, "后山", 5000, 20000, 1))
    await activity.record_window(uid, "explore", "后山", 5000, 20000)

    now = 1000 + 5 * 3600
    row = await db.fetchone("SELECT * FROM characters WHERE user_id=?", (uid,))
    baseline = settle.seclusion_gain(row["realm"], row["stage"], 4600, now,
                                     root_bone=row["root_bone"])
    res = await character.touch_activity(uid, "explorer", now=now)

    assert 0 < res["auto_cultivation"] < baseline
    char = await character.get_at(uid, now=now)
    assert char.cultivation == res["auto_cultivation"]
    assert not char.seclusion_at
