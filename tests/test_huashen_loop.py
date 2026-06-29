from config import realms as R
from config.bosses import boss_key_for_realm, WORLD_BOSSES
from config.dungeons import DUNGEONS
from config.items import ITEMS
from config.recipes import RECIPES
from tools import balance_sim as B


def test_taixu_dungeon_config_complete():
    d = DUNGEONS["taixu"]

    assert d["name"] == "太虚天门"
    assert d["realm"] == 4
    assert d["layers"] == 5
    assert d["stamina"] <= R.STAMINA_CAP[4] // 3
    assert d["entry_stone"] == 1800
    drops = {row[0] for row in d["drops"]}
    assert {"星陨砂", "幽都魂晶", "天外残玉", "转修令"} <= drops


def test_huashen_world_boss_config_complete():
    assert boss_key_for_realm(4) == "huashen"
    boss = WORLD_BOSSES["huashen"]

    assert boss["name"] == "天外魔尊"
    assert boss["realm"] == 4
    assert boss["stamina"] == 18
    assert {"星陨砂", "幽都魂晶", "天外残玉", "转修令"} <= set(boss["drops"])


def test_huashen_equipment_and_recipes_exist():
    for key in ("陨星剑", "幽都甲", "太虚佩"):
        assert key in ITEMS
        assert ITEMS[key]["type"] == "equipment"
        assert ITEMS[key]["tier"] == "玄"
    for recipe in ("forge_huashen_sword", "forge_huashen_armor", "forge_huashen_accessory"):
        assert recipe in RECIPES
        assert RECIPES[recipe]["realm"] == 4
        assert RECIPES[recipe]["output"]["key"] in {"陨星剑", "幽都甲", "太虚佩"}


def test_huashen_geared_profile_improves_stats():
    base = B.build_player_stats(4, 0, B.GEARED)
    geared = B.build_player_stats(4, 0, B.HUASHEN_GEARED)

    assert geared["atk"] > base["atk"]
    assert geared["hp"] > base["hp"]
    assert geared["df"] > base["df"]


def test_taixu_entry_and_full_clear_fraction_targets():
    entry = B.dungeon_clear_fraction(4, 0, "taixu", profile=B.HUASHEN_GEARED, n=80)
    full = B.dungeon_clear_fraction(4, R.num_stages(4) - 1, "taixu", profile=B.HUASHEN_GEARED, n=80)

    assert 0.35 <= entry <= 0.80
    assert full >= 0.95


def test_huashen_world_boss_kill_challenges_target_range():
    challenges = B.world_boss_kill_challenges("huashen", 4, 2, n=80, profile=B.HUASHEN_GEARED)

    assert 20 <= challenges <= 80
