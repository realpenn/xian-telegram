import pytest
import pytest_asyncio

from models import db
from services import character, market


@pytest_asyncio.fixture
async def temp_db(tmp_path):
    await db.init_db(str(tmp_path / "market.db"))
    try:
        yield
    finally:
        await db.close_db()


@pytest.mark.asyncio
async def test_bound_items_cannot_be_listed(temp_db):
    uid = 9701
    await character.create(uid, "seller")
    await character.add_item(uid, "天魔令", 2, bound=1)

    res = await market.create_listing(uid, "天魔令", 1, 100, now=1000)

    assert res["status"] == "no_item"
    assert await character.item_qty(uid, "天魔令", bound=1) == 2


@pytest.mark.asyncio
async def test_market_buy_transfers_item_stone_and_tax(temp_db):
    seller, buyer = 9702, 9703
    await character.create(seller, "seller")
    await character.create(buyer, "buyer")
    await character.add_item(seller, "星陨砂", 3)
    await character.add_stone(buyer, 1000)
    before_seller = (await character.get(seller)).spirit_stone

    listing = await market.create_listing(seller, "星陨砂", 2, 200, now=1000)
    res = await market.buy(buyer, listing["listing_id"], now=1001)

    assert res["status"] == "ok"
    assert res["tax"] == 10
    assert await character.item_qty(buyer, "星陨砂", bound=0) == 2
    assert await character.item_qty(seller, "星陨砂", bound=0) == 1
    assert (await character.get(seller)).spirit_stone == before_seller + 190
    assert (await character.get(buyer)).spirit_stone == 900
    assert (await market.buy(9704, listing["listing_id"], now=1002))["status"] == "not_available"


@pytest.mark.asyncio
async def test_market_cancel_returns_items(temp_db):
    uid = 9704
    await character.create(uid, "cancel")
    await character.add_item(uid, "幽都魂晶", 2)

    listing = await market.create_listing(uid, "幽都魂晶", 2, 300, now=1000)
    assert await character.item_qty(uid, "幽都魂晶") == 0
    res = await market.cancel(uid, listing["listing_id"], now=1001)

    assert res["status"] == "ok"
    assert await character.item_qty(uid, "幽都魂晶") == 2
    assert (await market.cancel(uid, listing["listing_id"], now=1002))["status"] == "not_available"


@pytest.mark.asyncio
async def test_market_self_buy_and_no_stone_are_blocked(temp_db):
    seller, buyer = 9705, 9706
    await character.create(seller, "seller")
    await character.create(buyer, "poor")
    await character.add_item(seller, "天外残玉", 1)

    listing = await market.create_listing(seller, "天外残玉", 1, 500, now=1000)

    assert (await market.buy(seller, listing["listing_id"], now=1001))["status"] == "self_buy"
    assert (await market.buy(buyer, listing["listing_id"], now=1001))["status"] == "no_stone"
    assert await character.item_qty(seller, "天外残玉") == 0


@pytest.mark.asyncio
async def test_market_audit_flags_high_price(temp_db):
    uid = 9707
    await character.create(uid, "audit")
    await character.add_item(uid, "星陨砂", 1)
    await market.create_listing(uid, "星陨砂", 1, 2_000_000, now=1000)

    rows = await market.audit_suspicious()

    assert rows and rows[0]["price"] == 2_000_000


def test_market_tax_rate_positive():
    assert market.MARKET_TAX_RATE > 0
