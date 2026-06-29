import pytest
import pytest_asyncio

from config import realms as R
from models import db
from services import breakthrough, character, shop


@pytest_asyncio.fixture
async def temp_db(tmp_path):
    await db.init_db(str(tmp_path / "inventory-bound.db"))
    try:
        yield
    finally:
        await db.close_db()


@pytest.mark.asyncio
async def test_inventory_bound_rows_coexist_and_default_unbound(temp_db):
    uid = 9101
    await character.create(uid, "bound")

    await character.add_item(uid, "灵草", 2)
    await character.add_item(uid, "灵草", 3, bound=1)

    assert await character.item_qty(uid, "灵草") == 5
    assert await character.item_qty(uid, "灵草", bound=0) == 2
    assert await character.item_qty(uid, "灵草", bound=1) == 3
    assert await character.inventory(uid) == [("灵草", 5)]
    assert await character.inventory(uid, bound=0) == [("灵草", 2)]
    assert await character.inventory(uid, bound=1) == [("灵草", 3)]


@pytest.mark.asyncio
async def test_shop_sell_only_uses_unbound_inventory(temp_db):
    uid = 9102
    await character.create(uid, "seller")
    await character.add_item(uid, "灵草", 2, bound=1)
    await character.add_item(uid, "灵草", 1, bound=0)

    assert (await shop.sell(uid, "灵草", 2))["status"] == "no_item"
    sold = await shop.sell(uid, "灵草", 1)

    assert sold["status"] == "ok"
    assert await character.item_qty(uid, "灵草", bound=0) == 0
    assert await character.item_qty(uid, "灵草", bound=1) == 2


@pytest.mark.asyncio
async def test_breakthrough_consumes_bound_pill_before_unbound(temp_db):
    uid = 9103
    await character.create(uid, "advancer")
    await character.set_progress(uid, 0, R.num_stages(0) - 1, R.advance_cost(0, R.num_stages(0) - 1))
    await character.add_item(uid, "筑基丹", 1, bound=0)
    await character.add_item(uid, "筑基丹", 1, bound=1)

    res = await breakthrough.try_advance(uid, now=1000)

    assert res["status"] == "big_success"
    assert await character.item_qty(uid, "筑基丹", bound=1) == 0
    assert await character.item_qty(uid, "筑基丹", bound=0) == 1
