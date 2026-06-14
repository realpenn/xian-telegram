from config import realms as R
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
    g = settle.seclusion_gain(0, 0, 0, 100 * 3600, place_factor=1.0)
    assert g == R.advance_cost(0, 0) // 2


def test_seclusion_negative_elapsed():
    assert settle.seclusion_gain(0, 0, 1000, 500) == 0


def test_seclusion_rate_uses_current_stage_cost():
    low = settle.seclusion_gain(0, 0, 0, 3600)
    high = settle.seclusion_gain(0, 12, 0, 3600)
    assert high > low


def test_seclusion_half_hour_is_below_first_advance_cost():
    assert settle.seclusion_gain(0, 0, 0, 1800) < R.advance_cost(0, 0)


def test_two_twelve_hour_sessions_equal_one_stage_with_remainder():
    cost = R.advance_cost(0, 1)
    first, remainder = settle.seclusion_gain_with_remainder(0, 1, 0, 12 * 3600)
    second, remainder = settle.seclusion_gain_with_remainder(
        0, 1, 0, 12 * 3600, remainder_units=remainder)

    assert first + second == cost
    assert remainder == 0
