from config import realms as R


def test_realm4_config_complete():
    assert len(R.REALM_NAMES) == 5
    assert R.REALM_STAGES[4] == R.REALM_STAGES[3]
    assert R.STAMINA_CAP[4] == 240
    assert R.SECLUSION_STAGE_HOURS[4] == 96
    assert R._REALM_BASE_COST[4] == 450000
    assert 4 in R._ANCHORS
    assert R.BIG_BREAKTHROUGH[4] == {"pill": "化神丹", "base_rate": 0.50, "tribulation": True}


def test_realm4_progression_and_stats():
    assert R.next_stage(3, 3) == (4, 0)
    assert R.is_big_breakthrough(3, 3) is True
    assert R.next_stage(4, 3) is None
    assert R.is_big_breakthrough(4, 3) is False
    assert R.base_stats(4, 0)["hp"] == 24000
    assert R.base_stats(4, 3)["hp"] == 52000
