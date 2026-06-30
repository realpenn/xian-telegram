"""V2 审计修复回归（docs/plans/v2/audit.md）。

覆盖：A1 据点掉率合算、A4 丹修/器修真实生效、B3 化神丹残方配方。
"""
import random

import pytest
import pytest_asyncio

from config import realms as R
from config import shop as SHOP
from config.items import ITEMS
from models import db
from services import breakthrough, character, crafting, dao_path, items, sect_war


@pytest_asyncio.fixture
async def temp_db(tmp_path):
    await db.init_db(str(tmp_path / "audit.db"))
    try:
        yield
    finally:
        await db.close_db()


# ---- A1：据点 drop_pct 合算进掉率 ----

def test_total_drop_pct_includes_outpost():
    assert sect_war.total_drop_pct(0.0, {"drop_pct": 0.05}) == 0.05
    assert sect_war.total_drop_pct(0.10, {"drop_pct": 0.05}) == pytest.approx(0.15)
    assert sect_war.total_drop_pct(0.18, {"drop_pct": 0.05}) == 0.20   # 封顶 +20%
    assert sect_war.total_drop_pct(0.0, {}) == 0.0


# ---- A4 器修：forge_pct 放大炼器词条品质 ----

def test_forge_quality_scales_affixes():
    base = crafting._roll_affixes("陨星剑", 50, 5, rng=random.Random(7), quality_mult=1.0)
    boosted = crafting._roll_affixes("陨星剑", 50, 5, rng=random.Random(7), quality_mult=1.10)

    assert set(base) == set(boosted)
    assert all(boosted[k] >= base[k] for k in base)
    assert any(boosted[k] > base[k] for k in base)


# ---- A4 丹修：alchemy_pct 提升真实突破成功率 ----

@pytest.mark.asyncio
async def test_alchemy_path_raises_real_breakthrough_rate(temp_db, monkeypatch):
    # base_rate=0.50；丹修宗师 alchemy_pct=0.10 → 0.60。random 固定 0.55：
    # 有丹修 → 成功（进神魂劫）；无丹修 → 失败。证明 alchemy_pct 真实接入突破。
    async def setup(uid: str) -> int:
        await character.create(uid, "alc")
        await character.set_progress(uid, 3, 3, R.advance_cost(3, 3))
        await db.execute("UPDATE characters SET root_bone=50 WHERE user_id=?", (uid,))
        await character.add_item(uid, "化神丹", 1)
        return uid

    dao_uid, ctrl_uid = 7001, 7002
    await setup(dao_uid)
    await setup(ctrl_uid)
    await dao_path.unlock(dao_uid, "alchemy")
    await db.execute(
        "UPDATE dao_paths SET rank=4 WHERE user_id=? AND path_key='alchemy'", (dao_uid,))

    monkeypatch.setattr(random, "random", lambda: 0.55)
    dao_res = await breakthrough.try_advance(dao_uid)
    ctrl_res = await breakthrough.try_advance(ctrl_uid)

    assert dao_res["status"] == "tribulation_choice"   # 丹修加成把 0.55 拉进成功区
    assert ctrl_res["status"] == "big_fail"            # 无加成则失败


# ---- B3：残方→化神丹配方打通获取链 ----

@pytest.mark.asyncio
async def test_huashen_pill_recipe_converts_scraps(temp_db):
    assert "化神丹" not in SHOP.SHOP_ITEMS          # 维持反套利：不进 NPC 直售
    assert ITEMS["化神丹方"]["recipe"] == "huashen_pill"

    uid = 7003
    await character.create(uid, "danxiu")
    await character.set_progress(uid, 4, 0, 0)
    await character.add_stone(uid, 5000)
    await character.add_item(uid, "化神丹残方", 6)
    await character.add_item(uid, "妖丹", 4)
    await character.add_item(uid, "化神丹方", 1)

    learn = await items.use(uid, "化神丹方")
    assert learn["status"] in ("recipe_ok", "known_recipe")

    started = await crafting.start_job(uid, "huashen_pill", now=1000)
    assert started["status"] == "started"
    collected = await crafting.collect_ready(uid, now=1000 + started["seconds"])

    assert any(c["name"] == "化神丹" for c in collected)
    assert await character.item_qty(uid, "化神丹") == 1
    assert await character.item_qty(uid, "化神丹残方") == 0   # 残方被消费
