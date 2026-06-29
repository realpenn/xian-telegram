# V2-M1 化神闭环：太虚天门 + 化神 Boss + 化神装备

> 对应 spec-v2 §5.2、§5.3、§3.2 装备验收口径、§11。
> 目标：化神期有完整 PvE（秘境 + 世界 Boss）与群目标，化神装备让属性档真正落地。
> 前置：M0 已上线（化神配置 + 突破 + 历练图）。M1 不阻塞 M2，但 **M1 的化神门槛测试必须先于 M2 道途存在**，供回归。

---

## 任务清单

### T1.1 化神秘境 太虚天门（`config/dungeons.py`）
按 spec §5.2 新增 key `taixu`：

| 字段 | 取值 |
|---|---|
| name | 太虚天门 |
| realm | 4 |
| layers | 5 |
| stamina | 60 |
| entry_stone | 1800 |
| 每日次数 | 2（走现有 `dungeon_runs` 日限机制） |
| stone / cult | 由 balance_sim 反推，受反套利约束 |
| drops | 化神丹材料、转修令（M2 才有语义，M1 先占位或暂不掉）、道途材料、化神法宝、飞升点材料（M3 才消费） |

- 怪物/Boss 数值由 T1.5 实跑反推。
- 每日 2 次上限：确认 `services/dungeon.py` 的日限读 `config` 而非硬编码；如硬编码需参数化。

**验收**（`tests/test_balance.py` + `tests/test_economy.py`）：
- 化神初期锚点（M1 用化神 GEARED 档，见 T1.4）：`dungeon_clear_fraction` 平均推进 **40%~70%**。
- 化神圆满：稳定通关（接近 100%）。
- 入场费 + 每日 2 次的灵石净收支：经 balance_sim 校验**不形成"刷秘境回本买精力"套利**（净灵石/精力 < 化神首买价）。
- 日常精力占用自洽：60×2=120 ≤ 化神精力上限 240，留出一次化神 Boss（18）+ 少量历练（spec §5.2 设计目标）。

### T1.2 化神世界 Boss 档（`config/bosses.py` + `services/world_boss.py`）
按 spec §5.3 新增档 `huashen`：

- `WORLD_BOSSES["huashen"] = {name:"天外魔尊", realm:4, total_hp:…, duration:2*3600, stamina:18, stone_pool:…, drops:{…}, combat:{…极高 hp 假人…}}`。
- `_REALM_TIER[4] = "huashen"`（**审查结论 C-6：spec §9.1 漏列**）。
- `total_hp` 按 `config/bosses.py` 既有口径反推：目标群规模 × 人均挑战次数 × 化神后期单次 chip 伤害（落在击杀 20~80 次区间）。
- 沿用同群独立、按 `cultivator_count` 缩放（`_scaled_total_hp`，无需改 `services/world_boss.py` 逻辑，仅加档）。
- drops 含化神材料、道途材料、飞升点材料；前列特殊奖励可掉化神丹材料（补 M0 来源）。

**验收**（`tests/test_balance.py`，复用 `world_boss_kill_challenges`）：
- `world_boss_kill_challenges("huashen", 4, 后期)` 落在 **20~80 次**。
- `boss_key_for_realm(4)=="huashen"`。
- 小群（cultivator_count 小）缩放后不出现"奖励独归榜首"（沿用现有小群前列特殊奖励逻辑，加断言覆盖化神档）。

### T1.3 化神装备与材料（`config/items.py`、`config/equipment.py`、`config/recipes.py`）
- 新增化神法宝/防具/饰品（hp/atk/df 平加 + 少量词条），来源：太虚天门、化神 Boss、化神难图。
- 强化/重铸沿用现有 `ENHANCE_PER_LEVEL` 管线（`services/equipment.py`），无需新机制。
- 化神丹方/装备图纸进 drops，不进 NPC 直售。

**验收**：`tests/test_combat`/`test_balance`：化神装备装上后，化神圆满属性接近 `_ANCHORS[4]` 圆满 + 装备的合理区间；不越过 §6.3 攻击/生存合算上限的预留余量（M1 先按"无道途"档校验，给 M2 留头寸）。

### T1.4 化神 GEARED 平衡档（`tools/balance_sim.py`）
spec §3.2：M1 化神装备上线后新增化神 GEARED 档并回归重调。
- 新增 `HUASHEN_GEARED`（化神装备 + 化神功法）profile。
- 把 M0 用"现役元婴装备近似"调出的化神图门槛，按 `HUASHEN_GEARED` **回归重调**（化神初期 GEARED 能稳刷易图、推进中图；圆满 GEARED 通难图）。
- 保留 M0 的 `YUANYING_FULL_BUFF` 上界断言（元婴圆满满 buff 仍 <5% 稳刷化神中/难 Boss）。

**验收**：`tests/test_balance.py` 化神三图 + 太虚天门 + 化神 Boss 的断言全部基于 `HUASHEN_GEARED` 重新固定，且 `python -m tools.balance_sim` 报告化神档数值合理。

### T1.5 化神内容数值定稿（贯穿 T1.1~T1.4）
- 用 balance_sim 迭代反推 太虚天门 / 化神 Boss / 化神装备的怪物与掉落数值，直到 T1.1/T1.2/T1.4 全部验收通过。
- 修为收益曲线：化神图 > 元婴图，避免回头刷低阶最优（spec §5.1）。

### T1.6 神魂劫"放开心魔"可选增强（从 M0 挪入，可选）
若产品要保留 spec §3.3 的"放开心魔"：
- `tribulation_sessions` 加列（`_ensure_column` 幂等）：`reward_mult REAL DEFAULT 1.0` 或 `risk_stack INTEGER`。
- `config/events.py` 神魂劫加 `放开心魔`：本段提高承伤、若撑过则累积 reward_mult。
- `choose_tribulation_action` 成功结算时按 reward_mult 放大奖励（额外修为/材料）。
**验收**：`test_shenhun_abandon_heart`：选"放开心魔"撑过 → 最终奖励高于全程稳健；中途血尽 → 仍轻惩罚不跌境。
> 非必须；若不做，删除本任务即可，不影响 M1 闭环。

---

## M1 完成定义（DoD）

1. `python -m pytest` 全绿，化神门槛/秘境/Boss/装备测试齐备并基于 `HUASHEN_GEARED`。
2. `python -m tools.balance_sim`：化神三图、太虚天门、化神 Boss 数值落在目标区间，套利全堵。
3. 化神玩家日常闭环成立：历练（化神三图）+ 太虚天门 ×2 + 化神世界 Boss，精力分配自洽。
4. 无破坏性 schema 改动（仅 `_ensure_column` 加列，若做 T1.6）。

## 风险与回避

| 风险 | 回避 |
|---|---|
| M2 道途 buff 上线后回溯打穿 M1 化神门槛 | M1 门槛预留 §6.3 合算上限的头寸；M2 落 clamp 后**回归 M1 化神测试**（README 跨里程碑依赖） |
| 太虚天门入场费 + 掉落形成套利 | T1.1 净收支进 balance_sim + test_economy |
| 化神 Boss total_hp 与假人尺度再次错配 | 沿用 `config/bosses.py` 既有"chip 伤害反推 total_hp"口径，勿手填 |
