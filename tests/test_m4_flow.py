import pytest
import pytest_asyncio

from config import buffs as BUFFS
from config import weekly_events as W
from models import db
from services import character, pvp, season, sect, sect_war, settle, weekly_events

# 落在据点战开放窗口内（周六 20:30，上海时区）的确定性时间戳。
WAR_OPEN = 1641040200


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
    await character.set_progress(uid, 4, 0, 0)
    await db.execute(
        "UPDATE characters SET stamina=?, stamina_at=? WHERE user_id=?",
        (W.RUN_STAMINA_COST * 4, 1000, uid))

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

    open_key = weekly_events.current_theme_key(2000)
    await weekly_events.run(uid, open_key, now=2000)
    row = await db.fetchone(
        "SELECT kind, source_key FROM activity_windows WHERE user_id=?",
        (uid,))

    assert row["kind"] == "weekly_activity"
    assert row["source_key"] == open_key


@pytest.mark.asyncio
async def test_weekly_activity_settles_stamina_regen_before_cost(temp_db):
    uid = 9615
    await character.create(uid, "regen")
    await db.execute(
        "UPDATE characters SET stamina=?, stamina_at=? WHERE user_id=?",
        (0, 1000, uid))
    now = 1000 + W.RUN_STAMINA_COST * settle.STAMINA_REGEN_SECONDS
    open_key = weekly_events.current_theme_key(now)

    res = await weekly_events.run(uid, open_key, now=now)
    row = await db.fetchone(
        "SELECT stamina, stamina_at, daohang FROM characters WHERE user_id=?",
        (uid,))

    assert res["status"] == "ok"
    assert row["stamina"] == 0
    assert row["stamina_at"] == now
    assert row["daohang"] == res["daohang"]


@pytest.mark.asyncio
async def test_weekly_theme_rotates_and_rejects_closed(temp_db):
    uid = 9607
    await character.create(uid, "rotate")
    await db.execute("UPDATE characters SET stamina=? WHERE user_id=?", (500, uid))

    # 不同周轮换出不同主题。
    keys = {weekly_events.current_theme_key(wk * 7 * 86400 + 1000) for wk in range(3)}
    assert len(keys) == len(W.WEEKLY_THEMES)

    open_key = weekly_events.current_theme_key(1000)
    closed_key = next(k for k in W.WEEKLY_THEMES if k != open_key)
    ok = await weekly_events.run(uid, open_key, now=1000)
    closed = await weekly_events.run(uid, closed_key, now=1000)

    assert ok["status"] == "ok"
    assert closed["status"] == "closed"
    assert closed["open"] == open_key


@pytest.mark.asyncio
async def test_sect_outpost_capture_adds_buff_under_clamp(temp_db):
    uid = 9603
    await character.create(uid, "leader")
    await character.set_progress(uid, 1, 0, 0)
    await character.add_stone(uid, 1000)
    await sect.create(uid, "战宗", now=1000)
    base = await character.stats(await character.get(uid))

    res = await sect_war.capture(uid, "altar", score=20, now=WAR_OPEN)
    buffed = await character.stats(await character.get(uid))
    raw = base["atk"]

    assert res["status"] == "ok"
    assert buffed["atk"] > base["atk"]
    assert buffed["atk"] <= int(raw * (1 + BUFFS.ATTACK_PCT_CAP))


@pytest.mark.asyncio
async def test_sect_war_closed_outside_window(temp_db):
    uid = 9613
    await character.create(uid, "closed")
    await character.set_progress(uid, 1, 0, 0)
    await character.add_stone(uid, 1000)
    await sect.create(uid, "时窗宗", now=1000)

    # now=1000 为周四上午，窗口外。
    closed = await sect_war.capture(uid, "altar", now=1000)
    opened = await sect_war.capture(uid, "altar", now=WAR_OPEN)

    assert closed["status"] == "closed"
    assert opened["status"] == "ok"


@pytest.mark.asyncio
async def test_sect_can_hold_multiple_outposts(temp_db):
    uid = 9614
    await character.create(uid, "multi")
    await character.set_progress(uid, 1, 0, 0)
    await character.add_stone(uid, 1000)
    await sect.create(uid, "多据点宗", now=1000)

    await sect_war.capture(uid, "altar", now=WAR_OPEN)
    await sect_war.capture(uid, "mine", now=WAR_OPEN)
    bonuses = await sect_war.bonuses_for_user(uid)

    # 两个据点 buff 并存：祭坛 stat_pct + 矿脉 drop_pct。
    assert bonuses.get("stat_pct") == 0.05
    assert bonuses.get("drop_pct") == 0.05


@pytest.mark.asyncio
async def test_sect_outpost_seclusion_buff_improves_gain(temp_db):
    uid = 9604
    await character.create(uid, "cave")
    await character.set_progress(uid, 1, 0, 0)
    await character.add_stone(uid, 1000)
    await sect.create(uid, "洞府宗", now=1000)
    await sect_war.capture(uid, "cave", now=WAR_OPEN)
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


@pytest.mark.asyncio
async def test_season_settle_monthly_only_rewards_participants(temp_db):
    fighter, idler = 9608, 9609
    await character.create(fighter, "fighter")
    await character.create(idler, "idler")
    # fighter 参与过天梯（有胜负记录），idler 没有。
    async with db.transaction() as conn:
        await pvp.ensure_rating(conn, fighter)
        await conn.execute("UPDATE pvp_ratings SET wins=1 WHERE user_id=?", (fighter,))

    granted = await season.settle_monthly(now=1000)
    again = await season.settle_monthly(now=1001)

    assert fighter in granted
    assert idler not in granted
    assert again == []   # 同赛季幂等，不重复发放
    frow = await db.fetchone("SELECT daohang FROM characters WHERE user_id=?", (fighter,))
    irow = await db.fetchone("SELECT daohang FROM characters WHERE user_id=?", (idler,))
    assert frow["daohang"] == season.SEASON_DAOHANG_REWARD
    assert irow["daohang"] == 0
