"""经济回归测试(#16):买精力阶梯价/每日上限。

补灵丹（原回精力，#16 有每日上限）已于 #24 改为回法力、脱离经济，相关用例移至 test_vitals。
#28：商店在炼气期供应疗伤丹/补灵丹（筑基前半价、筑基后全价），相关用例见文件末尾。
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


@pytest.mark.asyncio
async def test_recovery_pills_buyable_in_qi_at_half_price(temp_db):
    """#28：炼气期能在商店买到疗伤丹/补灵丹（补给不再断档），且筑基前半价。"""
    uid = 5005
    await character.create(uid, "tester")  # 默认炼气期 realm 0
    await character.add_stone(uid, 1000)

    # 取价函数：炼气期半价（25/30），筑基起全价（50/60）。
    assert shop_cfg.shop_price("疗伤丹", 0) == 25
    assert shop_cfg.shop_price("补灵丹", 0) == 30
    assert shop_cfg.shop_price("疗伤丹", 1) == 50
    assert shop_cfg.shop_price("补灵丹", 1) == 60

    # 炼气期实买：不再返回 locked，按半价扣费并入袋。
    res = await shop.buy(uid, "疗伤丹")
    assert res["status"] == "ok" and res["cost"] == 25
    res = await shop.buy(uid, "补灵丹")
    assert res["status"] == "ok" and res["cost"] == 30
    assert await character.item_qty(uid, "疗伤丹") == 1
    assert await character.item_qty(uid, "补灵丹") == 1

    # 商店列表向炼气期玩家展示这两味并标注半价。
    text, _ = await shop_handler.render_shop(uid)
    assert "疗伤丹：25 灵石（炼气期半价）" in text
    assert "补灵丹：30 灵石（炼气期半价）" in text


@pytest.mark.asyncio
async def test_recovery_pills_full_price_after_foundation(temp_db):
    """#28：筑基后恢复丹全价（50/60），保证 /craft 自炼仍更省。"""
    uid = 5006
    await character.create(uid, "tester")
    await character.set_progress(uid, 1, 0, 0)  # 筑基期 realm 1
    await character.add_stone(uid, 1000)

    res = await shop.buy(uid, "疗伤丹")
    assert res["status"] == "ok" and res["cost"] == 50
    res = await shop.buy(uid, "补灵丹")
    assert res["status"] == "ok" and res["cost"] == 60

    text, _ = await shop_handler.render_shop(uid)
    assert "（炼气期半价）" not in text
