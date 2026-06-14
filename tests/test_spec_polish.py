import pytest
import pytest_asyncio

from config import realms as R
from models import db
from services import breakthrough, character, explore, sect, world_boss


@pytest_asyncio.fixture
async def temp_db(tmp_path):
    await db.init_db(str(tmp_path / "polish-test.db"))
    try:
        yield
    finally:
        await db.close_db()


@pytest.mark.asyncio
async def test_breakthrough_failure_sets_unstable_debuff(temp_db, monkeypatch):
    uid = 4001
    await character.create(uid, "tester")
    last_qi = R.num_stages(0) - 1
    await character.set_progress(uid, 0, last_qi, R.advance_cost(0, last_qi))
    await character.add_item(uid, "筑基丹", 1)
    before = await character.stats(await character.get(uid))
    monkeypatch.setattr(breakthrough.random, "random", lambda: 0.99)

    res = await breakthrough.try_advance(uid)
    after_char = await character.get(uid)
    after = await character.stats(after_char)

    assert res["status"] == "big_fail"
    assert after_char.debuff_json["unstable_until"] > 0
    assert after["atk"] < before["atk"]


@pytest.mark.asyncio
async def test_tribulation_success_returns_three_logs(temp_db, monkeypatch):
    uid = 4002
    await character.create(uid, "tester")
    last_zj = R.num_stages(1) - 1
    await character.set_progress(uid, 1, last_zj, R.advance_cost(1, last_zj))
    await character.add_item(uid, "金丹", 1)
    monkeypatch.setattr(breakthrough.random, "random", lambda: 0.0)

    res = await breakthrough.try_advance(uid)

    assert res["status"] == "big_success"
    assert res["tribulation"]
    assert len(res["tribulation_log"]) == 3


@pytest.mark.asyncio
async def test_sect_welfare_affects_stats_and_seclusion(temp_db):
    uid = 4003
    await character.create(uid, "tester")
    await character.set_progress(uid, 1, 0, 0)
    await character.add_stone(uid, 500)
    before = await character.stats(await character.get(uid))

    assert (await sect.create(uid, "福利宗", now=1000))["status"] == "ok"
    after = await character.stats(await character.get(uid))
    assert after["hp"] > before["hp"]

    await character.start_seclusion(uid, now=1000)
    await db.execute("UPDATE characters SET seclusion_at=? WHERE user_id=?", (1000, uid))
    char = await character.get(uid)
    res = await character.collect_seclusion(uid, now=4600)
    assert res["gained"] > 600 * (1 + char.root_bone / 200)


class _FakeRng:
    def random(self):
        return 1.0

    def randint(self, low, high):
        if (low, high) == (1, 3):
            return 3
        return low

    def choice(self, values):
        return values[0]


@pytest.mark.asyncio
async def test_explore_can_run_three_encounters(temp_db):
    uid = 4004
    await character.create(uid, "tester")
    await character.set_progress(uid, 1, 0, 0)

    res = await explore.explore(uid, "后山", rng=_FakeRng())

    assert res["status"] == "ok"
    assert any("第 3 战" in line for line in res["log"])


@pytest.mark.asyncio
async def test_world_boss_scheduled_spawn_uses_known_chats(temp_db):
    class FakeBot:
        def __init__(self):
            self.sent = []

        async def send_message(self, chat_id, text):
            self.sent.append((chat_id, text))

    await world_boss.remember_chat(-4005, "试炼群", now=1000)
    bot = FakeBot()

    spawned = await world_boss.scheduled_spawn(bot, now=1000)

    assert spawned
    assert bot.sent and bot.sent[0][0] == -4005
