from services import settle


def test_regen_basic():
    val, at = settle.regen_stamina(0, 0, 100, 240 * 5)
    assert val == 5
    assert at == 240 * 5


def test_regen_caps_at_now():
    val, at = settle.regen_stamina(98, 0, 100, 240 * 100)
    assert val == 100
    assert at == 240 * 100


def test_regen_no_elapsed():
    assert settle.regen_stamina(10, 1000, 100, 1000) == (10, 1000)


def test_regen_anchor_keeps_remainder():
    # 250s -> +1，锚点只前移 240，剩 10s 不丢
    val, at = settle.regen_stamina(0, 0, 100, 250)
    assert val == 1
    assert at == 240


def test_regen_already_full():
    assert settle.regen_stamina(100, 0, 100, 999999) == (100, 999999)


def test_seclusion_offline_cap():
    g = settle.seclusion_gain(0, 0, 100 * 3600, root_bone=50, place_factor=1.0)
    rate = 200 * (1 + 50 / 200)  # 炼气速率 × 根骨系数
    assert g == int(rate * settle.OFFLINE_CAP_HOURS)


def test_seclusion_negative_elapsed():
    assert settle.seclusion_gain(0, 1000, 500, 50) == 0


def test_seclusion_root_bone_scales():
    low = settle.seclusion_gain(0, 0, 3600, root_bone=40)
    high = settle.seclusion_gain(0, 0, 3600, root_bone=80)
    assert high > low
