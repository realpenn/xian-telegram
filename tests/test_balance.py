"""数值平衡回归测试(#15)。

基于 tools.balance_sim(纯函数、固定 seed → 确定值)。覆盖入门/中期/圆满
三个阶段的地图、秘境胜率,以及闭关按境界配时长。

设计说明:战斗引擎含 15% 最大生命的治疗 + 1.8x 爆发技,单场胜负近乎二值
(非连续概率)。因此"普通小怪可刷、Boss 作为成长门槛"用如下稳定口径表达:
小怪单场必胜(可参与新图)、连战可刷;秘境入门能推进半数以上层数,
个别档位可接近通关;Boss 入门打不动、本境界中后期能过。
"""
from config import realms as R
from tools import balance_sim as B

MAP_OF = {1: "妖兽森林", 2: "万妖岭", 3: "上古战场"}
DGN_OF = {1: "xuanming", 2: "qingyun", 3: "tianxu"}


# ---- 闭关按境界配时长(#15-1) ----

def test_seclusion_stage_seconds_increases_with_realm():
    secs = [R.seclusion_stage_seconds(r) for r in range(4)]
    assert secs == [16 * 3600, 24 * 3600, 36 * 3600, 48 * 3600]
    assert secs == sorted(secs)  # 越高境界每小阶越慢,抵消"小阶少→偏快"


# ---- 刚突破即可参与新图普通内容(#15-2/3,核心验收) ----

def test_entry_small_mobs_are_farmable():
    for r in (1, 2, 3):
        mob, _ = B.map_winrates(r, 0, MAP_OF[r])
        assert mob >= 0.99, f"r{r} 刚解锁小怪单场胜率过低: {mob:.2f}"
        run = B.map_run_winrate(r, 0, MAP_OF[r])
        assert run >= 0.65, f"r{r} 刚解锁小怪连战胜率过低(刷不动): {run:.2f}"


def test_full_realm_small_mobs_trivial():
    for r in (1, 2, 3):
        last = R.num_stages(r) - 1
        assert B.map_run_winrate(r, last, MAP_OF[r]) >= 0.98


# ---- 地图随机 Boss 作为成长门槛(#15-2) ----

def test_map_boss_is_a_gate():
    for r in (1, 2, 3):
        last = R.num_stages(r) - 1
        entry = B.winrate(r, 0, _boss(r))
        full = B.winrate(r, last, _boss(r))
        assert entry <= 0.35, f"r{r} 刚解锁 Boss 太易({entry:.2f}),失去门槛意义"
        assert full >= 0.85, f"r{r} 圆满仍打不过 Boss({full:.2f})"


def test_map_boss_beatable_by_mid_realm():
    # 至少在本境界中期(stage1)起能稳定击杀随机 Boss。
    for r in (1, 2, 3):
        assert B.winrate(r, 1, _boss(r)) >= 0.85


# ---- 秘境入门可过半数层、圆满稳定通关(#15-2) ----

def test_dungeon_entry_clear_fraction_in_band():
    for r in (1, 2, 3):
        frac = B.dungeon_clear_fraction(r, 0, DGN_OF[r])
        assert 0.45 <= frac <= 0.95, f"r{r} 秘境入门通关层比例越界: {frac:.2f}"


def test_dungeon_full_realm_clears():
    for r in (1, 2, 3):
        last = R.num_stages(r) - 1
        assert B.dungeon_clear_fraction(r, last, DGN_OF[r]) >= 0.95


# ---- 世界 Boss 分档:击杀所需挑战次数落在 10-20 人 × 2-4 次区间(#14) ----

def test_world_boss_tiers_killable_in_target_range():
    from config.bosses import WORLD_BOSSES
    for key, cfg in WORLD_BOSSES.items():
        r = cfg["realm"]
        typ = min(2, R.num_stages(r) - 1)        # 典型参与者=后期
        n_typ = B.world_boss_kill_challenges(key, r, typ)
        assert 20 <= n_typ <= 80, f"{key} 后期击杀需 {n_typ:.0f} 次,超出 10-20人x2-4次区间"


def test_world_boss_total_hp_scaled_not_one_shot():
    # total_hp 与战斗假人尺度统一后,圆满玩家也无法一两次清空血池(否则失去群体意义)。
    from config.bosses import WORLD_BOSSES
    for key, cfg in WORLD_BOSSES.items():
        r = cfg["realm"]
        last = R.num_stages(r) - 1
        assert B.world_boss_kill_challenges(key, r, last) >= 8


# ---- 经济:买精力不能成为刷钱燃料(#16) ----

def test_buy_stamina_costlier_than_best_content_yield():
    """首买精力的单位成本须高于该境界最佳内容的灵石/精力产出,
    使"买精力→刷最佳内容"平均净收益为负(不能稳定套利)。"""
    from services import shop
    for r in range(4):
        cost = shop.first_buy_cost_per_stamina(r)
        yield_per = B.best_content_stone_per_stamina(r)
        assert cost > yield_per, (
            f"r{r} 首买 {cost:.1f} 灵石/精力 未高于最佳产出 {yield_per:.1f}，仍可套利")


def _boss(realm: int):
    from config.maps import MAPS
    return MAPS[MAP_OF[realm]]["boss"]
