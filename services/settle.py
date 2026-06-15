"""惰性结算：精力恢复、闭关修为。纯函数，便于单测（spec §4）。"""
from __future__ import annotations

from config import realms as R

STAMINA_REGEN_SECONDS = 216   # 1 点 / 3.6 分钟，约 400 点 / 日
OFFLINE_CAP_HOURS = 12        # 闭关离线上限
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
                                  remainder_units: int = 0) -> tuple[int, int]:
    """当前小阶 24 小时约得一级；根骨/外部加成再提速。"""
    elapsed = min(now - start_at, offline_cap_hours * 3600)
    if elapsed < 0:
        elapsed = 0
    raw_units = int(
        R.advance_cost(realm, stage)
        * elapsed
        * (1 + max(0, root_bone) / 200)
        * max(0.0, place_factor)
        * CULTIVATION_SCALE
        / R.seclusion_stage_seconds(realm)
    )
    total_units = raw_units + max(0, int(remainder_units or 0))
    return total_units // CULTIVATION_SCALE, total_units % CULTIVATION_SCALE
