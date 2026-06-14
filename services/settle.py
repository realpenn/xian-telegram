"""惰性结算：精力恢复、闭关修为。纯函数，便于单测（spec §4）。"""
from __future__ import annotations

from config.realms import SECLUSION_RATE

STAMINA_REGEN_SECONDS = 216   # 1 点 / 3.6 分钟，约 400 点 / 日
OFFLINE_CAP_HOURS = 12        # 闭关离线上限


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


def seclusion_gain(realm: int, start_at: int, now: int,
                   root_bone: int, place_factor: float = 1.0,
                   offline_cap_hours: int = OFFLINE_CAP_HOURS) -> int:
    """闭关所得修为 = 速率 × min(经过, 离线上限)。速率含根骨与地点系数。"""
    rate = SECLUSION_RATE[realm] * (1 + root_bone / 200) * place_factor
    elapsed = min(now - start_at, offline_cap_hours * 3600)
    if elapsed < 0:
        elapsed = 0
    return int(rate * elapsed / 3600)
