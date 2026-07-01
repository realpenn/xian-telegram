import pytest
import pytest_asyncio

from handlers import (ascension as ascension_handler, bag as bag_handler,
                      craft as craft_handler, cultivate as cultivate_handler,
                      dao_path as dao_path_handler, dungeon as dungeon_handler,
                      explore as explore_handler, help as help_handler,
                      market as market_handler, me as me_handler,
                      quest as quest_handler, sect as sect_handler,
                      sect_war as sect_war_handler, shop as shop_handler,
                      skills as skills_handler, weekly_events as weekly_handler)
from handlers.common import main_menu, section_back_markup
from models import db
from services import character


@pytest_asyncio.fixture
async def temp_db(tmp_path):
    await db.init_db(str(tmp_path / "menu-unification.db"))
    try:
        yield
    finally:
        await db.close_db()


def _datas(markup):
    return [button.callback_data for row in markup.inline_keyboard for button in row]


PRIMARY_NAVS = {
    button.callback_data
    for row in main_menu().inline_keyboard
    for button in row
}


def _assert_compact_top_level_menu(markup):
    datas = set(_datas(markup))

    assert "nav:menu" in datas
    assert not (PRIMARY_NAVS & datas)


@pytest.mark.asyncio
async def test_top_level_feature_pages_do_not_embed_full_main_menu(temp_db):
    """#52：主菜单入口页只展示本页操作和返回主菜单，不再拼完整主菜单。"""
    uid = 5200
    await character.create(uid, "menu-tester")

    pages = [
        ("道行", await me_handler.render_me(uid)),
        ("闭关", await cultivate_handler.render_cultivate(uid)),
        ("历练", await explore_handler.render_menu(uid)),
        ("秘境", await dungeon_handler.render_dungeon(uid)),
        ("炼制", await craft_handler.render_craft(uid)),
        ("功法", await skills_handler.render_skills(uid)),
        ("商店", await shop_handler.render_shop(uid)),
        ("储物袋", await bag_handler.render_bag(uid)),
        ("悬赏", await quest_handler.render_quest(uid)),
        ("宗门", await sect_handler.render_sect(uid)),
        ("道途", await dao_path_handler.render_path(uid)),
        ("飞升", await ascension_handler.render_ascension(uid)),
        ("活动", await weekly_handler.render_weekly(uid)),
        ("坊市", await market_handler.render_market(uid)),
        ("宗门战", await sect_war_handler.render_sect_war(uid)),
    ]

    for name, (_text, markup) in pages:
        assert markup is not None, name
        _assert_compact_top_level_menu(markup)


@pytest.mark.asyncio
async def test_secondary_pages_keep_contextual_back_links_without_full_menu(temp_db):
    uid = 5201
    await character.create(uid, "submenu-tester")

    secondary_pages = [
        ("商店分类", await shop_handler.render_category(uid, "material"), {"nav:shop"}),
        ("坊市定价", await market_handler.render_price_editor(uid, "灵草", 100), {"nav:market"}),
        ("宗门商店", await sect_handler.render_sect_shop(uid), {"nav:sect"}),
    ]

    for name, (_text, markup), expected_back_links in secondary_pages:
        datas = set(_datas(markup))
        assert expected_back_links <= datas, name
        assert not ((PRIMARY_NAVS - expected_back_links) & datas), name
        assert "nav:menu" not in datas, name


def test_action_result_markup_returns_to_section_or_main_menu():
    markup = section_back_markup("↩️ 返回炼制", "nav:craft")

    assert _datas(markup) == ["nav:craft", "nav:menu"]
