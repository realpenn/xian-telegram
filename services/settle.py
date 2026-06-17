"""惰性结算：精力恢复、闭关修为。纯函数，便于单测（spec §4）。"""
from __future__ import annotations

from config import realms as R

STAMINA_REGEN_SECONDS = 216   # 1 点 / 3.6 分钟，约 400 点 / 日
OFFLINE_CAP_HOURS = 12        # 闭关离线上限
# 气血/法力自然回复（#24）：按 max 的百分比/分，跨境界自动缩放。
# 0→满 所需秒数：气血 2000s(3%/分)、法力 1000s(6%/分，快于气血)。
HP_REGEN_SECONDS_PER_FULL = 2000
MP_REGEN_SECONDS_PER_FULL = 1000
HP_FLOOR_PCT = 0.20           # 活动结束写回的重伤地板：胜负都不破 20%·maxHP
# 每小阶目标时长改为按境界配置（见 config.realms.seclusion_stage_seconds，#15）。
# 保留此常量作为基线（筑基档 24h），仅供外部参考。
SECLUSION_STAGE_SECONDS = 24 * 3600
CULTIVATION_SCALE = 1_000_000


def regen_stamina(stamina: int, stamina_at: int, cap: int, now: int):
    """按时间戳惰性恢复精力，返回 (新精力, 新锚点时间戳)。"""
    if stamina >= cap:
        return cap, now
    gained = (now - stamina_at) // STAMINA_REGEN_SECONDS
    if gained <= 0:
        return stamina, stamina_at
    new_val = min(cap, stamina + gained)
    # 锚点只前移已消耗的整数刻度，避免丢失零头进度。
    new_at = stamina_at + gained * STAMINA_REGEN_SECONDS
    if new_val >= cap:
        new_at = now
    return new_val, new_at


def regen_resource(cur: int, cap: int, at: int, now: int, seconds_per_full: int):
    """按时间惰性回复气血/法力（#24），返回 (新值, 新锚点)。

    速率 = cap / seconds_per_full（点/秒），故跨境界随 max 缩放。仿 regen_stamina：
    锚点只前移「已消耗整点」对应的时间，避免快读时零头被反复丢弃导致永不回复。
    """
    if cap <= 0:
        return 0, now
    if cur >= cap:
        return cap, now
    gained = int((now - at) * cap / seconds_per_full)
    if gained <= 0:
        return cur, at
    new_val = min(cap, cur + gained)
    consumed = int(gained * seconds_per_full / cap)
    new_at = at + consumed
    if new_val >= cap:
        new_at = now
    return new_val, new_at


def seclusion_gain(realm: int, stage: int, start_at: int, now: int,
                   root_bone: int = 0,
                   place_factor: float = 1.0,
                   offline_cap_hours: int = OFFLINE_CAP_HOURS) -> int:
    gain, _ = seclusion_gain_with_remainder(
        realm, stage, start_at, now, root_bone, place_factor, offline_cap_hours, 0)
    return gain


def seclusion_gain_with_remainder(realm: int, stage: int, start_at: int, now: int,
                                  root_bone: int = 0,
                                  place_factor: float = 1.0,
                                  offline_cap_hours: int = OFFLINE_CAP_HOURS,
                                  remainder_units: int = 0,
                                  activity_windows: list[tuple[int, int]] = None,
                                  active_factor: float = 1.0) -> tuple[int, int]:
    """当前小阶 24 小时约得一级；根骨/外部加成再提速。"""
    elapsed = min(now - start_at, offline_cap_hours * 3600)
    if elapsed < 0:
        elapsed = 0
    effective_elapsed = _effective_elapsed(
        start_at, start_at + elapsed, activity_windows or [], active_factor)
    raw_units = int(
        R.advance_cost(realm, stage)
        * effective_elapsed
        * (1 + max(0, root_bone) / 200)
        * max(0.0, place_factor)
        * CULTIVATION_SCALE
        / R.seclusion_stage_seconds(realm)
    )
    total_units = raw_units + max(0, int(remainder_units or 0))
    return total_units // CULTIVATION_SCALE, total_units % CULTIVATION_SCALE


def _effective_elapsed(start_at: int, finish_at: int,
                       activity_windows: list[tuple[int, int]],
                       active_factor: float) -> float:
    total = max(0, finish_at - start_at)
    if total <= 0 or not activity_windows:
        return total
    active_factor = max(0.0, min(1.0, float(active_factor)))
    merged = []
    for raw_start, raw_finish in sorted(activity_windows):
        s = max(start_at, int(raw_start))
        f = min(finish_at, int(raw_finish))
        if f <= s:
            continue
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], f))
        else:
            merged.append((s, f))
    active = sum(f - s for s, f in merged)
    return (total - active) + active * active_factor
