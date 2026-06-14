from services import settle


def test_regen_basic():
    val, at = settle.regen_stamina(0, 0, 100, settle.STAMINA_REGEN_SECONDS * 5)
    assert val == 5
    assert at == settle.STAMINA_REGEN_SECONDS * 5


def test_regen_caps_at_now():
    val, at = settle.regen_stamina(98, 0, 100, 240 * 100)
    assert val == 100
    assert at == 240 * 100


def test_regen_no_elapsed():
    assert settle.regen_stamina(10, 1000, 100, 1000) == (10, 1000)


def test_regen_anchor_keeps_remainder():
    # 多 10s -> +1，锚点只前移一个恢复刻度，剩余秒数不丢
    val, at = settle.regen_stamina(0, 0, 100, settle.STAMINA_REGEN_SECONDS + 10)
    assert val == 1
    assert at == settle.STAMINA_REGEN_SECONDS


def test_regen_daily_budget_is_about_400():
    val, _ = settle.regen_stamina(0, 0, 1000, 24 * 3600)
    assert val == 400


def test_regen_already_full():
    assert settle.regen_stamina(100, 0, 100, 999999) == (100, 999999)


def test_seclusion_offline_cap():
    g = settle.seclusion_gain(0, 0, 100 * 3600, root_bone=50, place_factor=1.0)
    rate = 15 * (1 + 50 / 200)  # 炼气速率 × 根骨系数
    assert g == int(rate * settle.OFFLINE_CAP_HOURS)


def test_seclusion_negative_elapsed():
    assert settle.seclusion_gain(0, 1000, 500, 50) == 0


def test_seclusion_root_bone_scales():
    low = settle.seclusion_gain(0, 0, 3600, root_bone=40)
    high = settle.seclusion_gain(0, 0, 3600, root_bone=80)
    assert high > low


def test_seclusion_half_hour_is_below_first_advance_cost():
    assert settle.seclusion_gain(0, 0, 1800, root_bone=60) < 200
