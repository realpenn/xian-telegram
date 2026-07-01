from config import buffs as BUFFS
from config import dao_paths as DAO
from config.maps import MAPS
from config import realms as R
from tools import balance_sim as B


def test_sword_path_leads_world_boss_damage_not_dungeon_tankiness():
    sword = B.DAO_MAX_PROFILES["sword"]
    body = B.DAO_MAX_PROFILES["body"]

    sword_damage = B.boss_damage_per_challenge(3, 3, "yuanying", profile=sword, n=80)
    body_damage = B.boss_damage_per_challenge(3, 3, "yuanying", profile=body, n=80)
    sword_dungeon = B.dungeon_clear_fraction(3, 0, "tianxu", profile=sword, n=80)
    body_dungeon = B.dungeon_clear_fraction(3, 0, "tianxu", profile=body, n=80)

    assert sword_damage > body_damage
    assert body_dungeon >= sword_dungeon


def test_body_path_leads_dungeon_clear_not_boss_damage():
    sword = B.DAO_MAX_PROFILES["sword"]
    body = B.DAO_MAX_PROFILES["body"]

    body_dungeon = B.dungeon_clear_fraction(2, 0, "qingyun", profile=body, n=80)
    sword_dungeon = B.dungeon_clear_fraction(2, 0, "qingyun", profile=sword, n=80)
    body_damage = B.boss_damage_per_challenge(3, 3, "yuanying", profile=body, n=80)
    sword_damage = B.boss_damage_per_challenge(3, 3, "yuanying", profile=sword, n=80)

    assert body_dungeon > sword_dungeon
    assert sword_damage > body_damage


def test_alchemy_path_leads_breakthrough_metric():
    alchemy = B.DAO_MAX_PROFILES["alchemy"]
    sword = B.DAO_MAX_PROFILES["sword"]

    assert B.breakthrough_rate_with_profile(0.50, alchemy) > B.breakthrough_rate_with_profile(0.50, sword)


def test_forge_path_leads_forge_metric():
    forge = B.DAO_MAX_PROFILES["forge"]
    sword = B.DAO_MAX_PROFILES["sword"]

    assert B.forge_quality_score(forge) > B.forge_quality_score(sword)


def test_talisman_path_leads_seclusion_metric():
    talisman = B.DAO_MAX_PROFILES["talisman"]
    body = B.DAO_MAX_PROFILES["body"]

    assert B.seclusion_efficiency(talisman) > B.seclusion_efficiency(body)


def test_max_dao_paths_remain_under_stat_caps():
    raw = R.base_stats(3, 3)
    profiles = list(B.DAO_MAX_PROFILES.values()) + list(B.DAO_MAX_REFINED_PROFILES.values())
    for profile in profiles:
        st = B.build_player_stats(3, 3, profile)
        assert st["atk"] <= int((raw["atk"] + 38) * (1 + BUFFS.ATTACK_PCT_CAP))
        assert st["hp"] <= int((raw["hp"] + 160) * (1 + BUFFS.SURVIVAL_PCT_CAP))


def test_each_dao_path_has_continuous_sink_metric():
    metrics = {
        "sword": B.boss_damage_per_challenge(3, 3, "yuanying", profile=B.DAO_MAX_PROFILES["sword"], n=40),
        "body": B.dungeon_clear_fraction(3, 0, "tianxu", profile=B.DAO_MAX_PROFILES["body"], n=40),
        "alchemy": B.breakthrough_rate_with_profile(0.50, B.DAO_MAX_PROFILES["alchemy"]),
        "forge": B.forge_quality_score(B.DAO_MAX_PROFILES["forge"]),
        "talisman": B.seclusion_efficiency(B.DAO_MAX_PROFILES["talisman"]),
    }

    assert set(metrics) == set(DAO.DAO_PATHS)
    assert all(value > 0 for value in metrics.values())


def test_refined_body_taixu_progression_is_modeled():
    base = B.dungeon_clear_fraction(
        4, 0, "taixu", profile=B.DAO_MAX_PROFILES["body"], n=80)
    refined = B.dungeon_clear_fraction(
        4, 0, "taixu", profile=B.DAO_MAX_REFINED_PROFILES["body"], n=80)

    assert refined >= base + 0.30
    assert refined < 0.90


def test_refined_sword_keeps_xingyun_entry_boss_gate():
    boss = MAPS["星陨海"]["boss"]
    base = B.winrate(4, 0, boss, profile=B.DAO_MAX_PROFILES["sword"], n=120)
    refined = B.winrate(4, 0, boss, profile=B.DAO_MAX_REFINED_PROFILES["sword"], n=120)

    assert refined <= base + 0.05
    assert refined < 0.75
