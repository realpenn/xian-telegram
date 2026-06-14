import pytest
import pytest_asyncio

from config import realms as R
from handlers.common import action_callback_data, consume_action_callback
from models import db
from services import breakthrough, character, crafting, explore, items, pvp, sect, shop, world_boss


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
async def test_equipped_treasure_improves_big_breakthrough_rate(temp_db, monkeypatch):
    uid = 4010
    await character.create(uid, "tester")
    char = await character.get(uid)
    last_qi = R.num_stages(0) - 1
    await character.set_progress(uid, 0, last_qi, R.advance_cost(0, last_qi))
    await character.add_item(uid, "筑基丹", 1)
    await character.create_item_instance(uid, "聚灵佩")
    inst = (await character.item_instances(uid))[0]
    await character.equip_instance(uid, inst["id"])
    monkeypatch.setattr(breakthrough.random, "random", lambda: 0.99)

    res = await breakthrough.try_advance(uid)

    assert res["status"] == "big_fail"
    assert res["rate"] > breakthrough.big_success_rate(0, char.root_bone)


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


@pytest.mark.asyncio
async def test_sect_leader_can_upgrade_with_contribution_pool(temp_db):
    uid = 4011
    await character.create(uid, "tester")
    await character.set_progress(uid, 1, 0, 0)
    await character.add_stone(uid, 500)
    assert (await sect.create(uid, "升阶宗", now=1000))["status"] == "ok"
    await db.execute("UPDATE sects SET contribution_pool=100 WHERE leader_user_id=?", (uid,))

    res = await sect.upgrade(uid)
    mine = await sect.my_sect(uid)

    assert res["status"] == "upgraded"
    assert mine["level"] == 2


def test_root_bone_roll_stays_in_spec_range():
    class Rng:
        def __init__(self, value):
            self.value = value

        def gauss(self, mean, stddev):
            return self.value

    assert character.roll_root_bone(Rng(1)) == 40
    assert character.roll_root_bone(Rng(999)) == 80
    assert character.roll_root_bone(Rng(60.2)) == 60


@pytest.mark.asyncio
async def test_pvp_random_opponent_prefers_rating_band(temp_db):
    uid = 4012
    close_uid = 4013
    far_uid = 4014
    for user_id in (uid, close_uid, far_uid):
        await character.create(user_id, f"u{user_id}")
    await db.execute(
        "INSERT INTO pvp_ratings(user_id, rating) VALUES(?, ?), (?, ?), (?, ?)",
        (uid, 1000, close_uid, 1100, far_uid, 1600))

    assert await pvp.random_opponent(uid) == close_uid


@pytest.mark.asyncio
async def test_pvp_opponent_arg_supports_username_and_rank(temp_db):
    attacker = 4017
    named = 4018
    ranked = 4019
    await character.create(attacker, "attacker")
    await character.create(named, "TargetDao")
    await character.create(ranked, "ranker")
    await db.execute(
        "INSERT INTO pvp_ratings(user_id, rating, wins) VALUES(?, ?, ?), (?, ?, ?)",
        (named, 1000, 0, ranked, 1500, 3))

    by_name = await pvp.opponent_from_arg("@targetdao")
    by_rank = await pvp.opponent_from_arg("#1")

    assert by_name["status"] == "ok"
    assert by_name["user_id"] == named
    assert by_rank["status"] == "ok"
    assert by_rank["user_id"] == ranked


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
    class SentMessage:
        def __init__(self, message_id):
            self.message_id = message_id

    class FakeBot:
        def __init__(self):
            self.sent = []
            self.edited = []

        async def send_message(self, chat_id, text):
            self.sent.append((chat_id, text))
            return SentMessage(len(self.sent))

        async def edit_message_text(self, text, chat_id, message_id):
            self.edited.append((chat_id, message_id, text))

    await world_boss.remember_chat(-4005, "试炼群", now=1000)
    bot = FakeBot()

    spawned = await world_boss.scheduled_spawn(bot, now=1000)
    await world_boss.scheduled_spawn(bot, now=1001)

    assert spawned
    assert bot.sent and bot.sent[0][0] == -4005
    assert len(bot.sent) == 1
    assert bot.edited and bot.edited[0][0] == -4005


@pytest.mark.asyncio
async def test_world_boss_expiry_distributes_participation_rewards(temp_db):
    uid = 4009
    await character.create(uid, "tester")
    boss = await world_boss.ensure_active(-4009, now=1000)
    before = (await character.get(uid)).spirit_stone
    await db.execute(
        "INSERT INTO world_boss_damage(boss_id, user_id, damage) VALUES(?,?,?)",
        (boss["id"], uid, 100))

    res = await world_boss.status(-4009, now=boss["expire_at"] + 1)
    after_first = (await character.get(uid)).spirit_stone
    await world_boss.status(-4009, now=boss["expire_at"] + 2)
    after_second = (await character.get(uid)).spirit_stone

    assert res["status"] == "expired"
    assert after_first > before
    assert after_second == after_first


@pytest.mark.asyncio
async def test_consumables_restore_clear_debuff_and_raise_root(temp_db):
    uid = 4006
    await character.create(uid, "tester")
    before = await character.get(uid)
    await db.execute(
        "UPDATE characters SET stamina=0, stamina_at=?, debuff_json=? WHERE user_id=?",
        (1000, '{"unstable_until":999999}', uid))
    await character.add_item(uid, "补灵丹", 1)
    await character.add_item(uid, "疗伤丹", 1)
    await character.add_item(uid, "天材地宝", 1)

    stamina_res = await items.use(uid, "补灵丹", now=1000)
    heal_res = await items.use(uid, "疗伤丹", now=1000)
    root_res = await items.use(uid, "天材地宝", now=1000)
    after = await character.get(uid)

    assert stamina_res["status"] == "stamina_ok"
    assert heal_res["status"] == "healed"
    assert root_res["status"] == "root_up"
    assert after.stamina > 0
    assert after.debuff_json == {}
    assert after.root_bone == before.root_bone + 1


@pytest.mark.asyncio
async def test_spirit_stones_can_buy_stamina(temp_db):
    uid = 4015
    await character.create(uid, "tester")
    await db.execute(
        "UPDATE characters SET stamina=0, stamina_at=?, spirit_stone=? WHERE user_id=?",
        (1000, 100, uid))

    res = await shop.buy_stamina(uid, now=1000)
    row = await db.fetchone("SELECT stamina, spirit_stone FROM characters WHERE user_id=?", (uid,))

    assert res["status"] == "stamina_ok"
    assert res["gain"] == shop.STAMINA_STONE_GAIN
    assert row["stamina"] == shop.STAMINA_STONE_GAIN
    assert row["spirit_stone"] == 100 - shop.STAMINA_STONE_COST


@pytest.mark.asyncio
async def test_user_last_seen_is_updated(temp_db):
    uid = 4016
    await character.create(uid, "old")

    await character.touch_user(uid, "new", now=1234)
    row = await db.fetchone(
        "SELECT username, last_seen_at FROM users WHERE tg_user_id=?",
        (uid,))

    assert row["username"] == "new"
    assert row["last_seen_at"] == 1234


@pytest.mark.asyncio
async def test_recipe_item_unlocks_non_default_crafting(temp_db):
    uid = 4007
    await character.create(uid, "tester")
    await character.set_progress(uid, 2, 0, 0)
    assert "forge_accessory" not in {
        key for key, _ in await crafting.available_recipes(uid)
    }

    await character.add_item(uid, "聚灵佩图纸", 1)
    res = await items.use(uid, "聚灵佩图纸", now=1000)

    assert res["status"] == "recipe_ok"
    assert "forge_accessory" in {
        key for key, _ in await crafting.available_recipes(uid)
    }


@pytest.mark.asyncio
async def test_callback_token_is_single_use(temp_db):
    class User:
        id = 4008

    class FakeCallback:
        def __init__(self, data):
            self.data = data
            self.from_user = User()
            self.answers = []

        async def answer(self, text=None, show_alert=False):
            self.answers.append((text, show_alert))

    data = await action_callback_data(User.id, "ex:后山")
    first = FakeCallback(data)
    second = FakeCallback(data)

    assert await consume_action_callback(first) == "ex:后山"
    assert await consume_action_callback(second) is None
    assert second.answers and second.answers[0][1] is True
