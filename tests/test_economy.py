"""经济回归测试(#16):买精力阶梯价/每日上限。

补灵丹（原回精力，#16 有每日上限）已于 #24 改为回法力、脱离经济，相关用例移至 test_vitals。
"""
import time

import pytest
import pytest_asyncio

from config import shop as shop_cfg
from handlers import shop as shop_handler
from models import db
from services import character, items, shop

DAY = 24 * 3600


@pytest_asyncio.fixture
async def temp_db(tmp_path):
    await db.init_db(str(tmp_path / "econ-test.db"))
    try:
        yield
    finally:
        await db.close_db()


async def _drain(uid):
    """把精力清零以便连续购买（不动 stamina_at，避免触发自然恢复）。"""
    await db.execute("UPDATE characters SET stamina=0 WHERE user_id=?", (uid,))


@pytest.mark.asyncio
async def test_buy_stamina_escalates_and_caps(temp_db):
    uid = 5001
    await character.create(uid, "tester")
    await character.set_progress(uid, 3, 0, 0)  # 元婴，基价最高便于看翻倍
    await db.execute(
        "UPDATE characters SET stamina=0, stamina_at=1000, spirit_stone=10_000_000 WHERE user_id=?",
        (uid,))

    costs = []
    for _ in range(shop_cfg.STAMINA_BUY_DAILY_LIMIT):
        await _drain(uid)
        res = await shop.buy_stamina(uid, now=1000)
        assert res["status"] == "stamina_ok"
        costs.append(res["cost"])

    # 当日第 n 次价格按 2 的幂翻倍递增。
    assert costs == [shop_cfg.stamina_buy_cost(3, n) for n in range(1, len(costs) + 1)]
    assert costs[1] == costs[0] * 2 and costs[2] == costs[1] * 2

    # 触达每日上限后拒绝。
    await _drain(uid)
    assert (await shop.buy_stamina(uid, now=1000))["status"] == "buy_limit"

    # 跨天重置回首买价。
    await db.execute("UPDATE characters SET stamina=0, stamina_at=? WHERE user_id=?", (1000 + DAY, uid))
    res = await shop.buy_stamina(uid, now=1000 + DAY)
    assert res["status"] == "stamina_ok"
    assert res["cost"] == shop_cfg.stamina_buy_cost(3, 1)


@pytest.mark.asyncio
async def test_render_shop_shows_next_stamina_buy_cost(temp_db):
    uid = 5003
    now = 1000
    today = time.strftime("%Y-%m-%d", time.localtime(now))
    await character.create(uid, "tester")
    await character.set_progress(uid, 3, 0, 0)

    await db.execute(
        "UPDATE characters SET stamina_buy_count=1, stamina_buy_day=? WHERE user_id=?",
        (today, uid))
    _, markup = await shop_handler.render_shop(uid, now=now)
    assert markup.inline_keyboard[0][0].text == (
        f"购买精力（🪙{shop_cfg.stamina_buy_cost(3, 2)} / ⚡{shop_cfg.STAMINA_BUY_GAIN}）")

    await db.execute(
        "UPDATE characters SET stamina_buy_count=2, stamina_buy_day=? WHERE user_id=?",
        (today, uid))
    _, markup = await shop_handler.render_shop(uid, now=now)
    assert markup.inline_keyboard[0][0].text == (
        f"购买精力（🪙{shop_cfg.stamina_buy_cost(3, 3)} / ⚡{shop_cfg.STAMINA_BUY_GAIN}）")
