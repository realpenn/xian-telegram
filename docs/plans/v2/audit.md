# V2 (M0–M5) 验收审计

> 基线：`uv run --with-requirements requirements.txt python -m pytest` 当前 **237 passed**。
> **C 轮**（C1–C4）已修复并落测试回归。
> **R 轮**（2026-06-30 深度 review）发现 2 个 P0 + 5 个 P1 + 7 个 P2；**P0/P1 已全部修复**（本分支），P2 待评估。

## C 轮：已修复（commit `3ddb458` / `5ad9690` / `4253777`）
- **P0/P1（8 项）** — `3ddb458`：据点掉率合算、丹修/器修真实接入突破与炼器、化神丹残方配方、sect_outposts 复合主键迁移、门派战窗口/多据点、月度结算等。
- **C2 / C3 / C1** — `5ad9690`：C2 红线回归（YUANYING_FULL_BUFF 元婴满 buff 打化神中/难 Boss <5%、幽都裂主数值上调）；C3 文案/播报（神魂劫 need_pill 来源指引、飞升试炼/被动升级播报 + 派生尊号）；C1 反套利（balance_sim 覆盖坊市灵石流/活动道行/飞升点）。
- **C4** — `4253777`：低境界含掉落微套利，根因为 balance_sim 秘境口径两处 bug（漏扣 entry_stone、drops 误乘 reward_factor）。修正后全境界 r0–r4 反套利红线成立，未改经济参数。

---

## R 轮：深度 review 新发现（2026-06-30）

> 范围：逐条对照 M0–M5 验收点 + 跨里程碑架构约束，对 config/services/handlers/tests 做代码级审查与运行时交叉验证。C 轮未覆盖玩家坊市绑定隔离与宗门战玩法完整性，本轮补上。

### 已修复（本分支 `fix/v2-audit-p0p1`）

- **R-P0-1 绑定隔离破洞** —— `config/items.py` 新增 `NO_TRADE`（转修令/化神丹/保命符）+ `is_tradable()`，`market.create_listing` 上架前拒绝限售物品（`no_trade`），坊市 UI 过滤同类物品。回归：`tests/test_market.py::test_key_materials_cannot_be_listed_even_unbound`。
- **R-P0-2 宗门战空心** —— `config/sect_war.py` 为每据点加守卫；`sect_war.capture` 复用战斗引擎，胜方才计积分、败方 `defeated` 无积分；新增 `settle_season()` 赛季结算（积分最高宗门成员得绑定道行，幂等），接入 `bot/app.py` 月末调度 + `sect_war_rewards` 表。回归：`test_sect_war_capture_requires_beating_guard`、`test_sect_war_season_settles_top_sect_once`。
- **R-P1-1** 天外墟主上调 `atk=7200, df=4800`（高于小怪），恢复难图 Boss 门槛语义。
- **R-P1-2** `ascension.trial` 加周冷却（`ascension.last_trial_week` 列 + `weekly_done`）。回归：`test_ascension_trial_weekly_cooldown`。
- **R-P1-3** 补两源：化神世界 Boss 前列按名次发飞升点（`world_boss._distribute`，`BOSS_RANK_POINTS`）；活动商店消耗活动材料兑飞升点（`weekly_events.exchange`）。回归：`test_huashen_world_boss_grants_ascension_points_to_top_ranks`、`test_activity_shop_exchanges_material_for_ascension_point`。
- **R-P1-4** `market.cancel` 补 `AND status='active'` + rowcount 守卫。
- **R-P1-5** `config/items.py` 定义保命符；`config/weekly_events.py` `SHOP_OFFERS` + `weekly_events.exchange` 提供活动商店兑换出口，`/weekly` UI 接入。回归：`test_activity_shop_*`。

### P2（瑕疵 / 设计偏差，可选）

- **R-P2-1** `config/dao_paths.py:11` 宗师档成本是 `daohang+天外残玉`，未接飞升点，偏离 spec §4.3"宗师=周期性飞升点投入"。注：宗师档**可达**（`rank_up` 在 `target_rank>=5` 才拦截），非死代码。
- **R-P2-2** `models/db.py:431-448` inventory 主键迁移未显式事务包裹，DROP/RENAME 间崩溃有理论丢表风险（概率极低）。
- **R-P2-3** `services/character.py:396-406` clamp `max(0, raw)` 会吞负向 buff（当前无 debuff，无实际危害）。
- **R-P2-4** 化神失败"不跌境"无测试断言（代码逻辑正确，缺回归保护）。
- **R-P2-5** `services/ascension.py:81` 尊号阈值过低（`level>=5` 即"渡劫仙尊"，单项点满即触发）。
- **R-P2-6** `services/market.py:99-103` 价格异常审计仅是高价列表查询，无异常判定/审计日志表。
- **R-P2-7** `tools/balance_sim.py` 反套利校验未覆盖玩家坊市路径（R-P0-1 的工具侧盲区）。

### 测试质量问题（剩余）

1. `tests/test_m3_flow.py` 名不副实：21 用例全是 PvP/Boss/宗门/日常，无飞升点内容；真正 M3 测试在 `test_ascension.py`。
2. 溢出分流 30%/20%/50% 数值无专门断言；cancel 竞态无并发测试。

### 里程碑完成度

| 里程碑 | 完成度 | 剩余瑕疵 |
|---|---|---|
| M0 满级止血 | ✅ | R-P2-4 缺测试 |
| M1 化神闭环 | ✅ | 测试 profile 口径分裂 |
| M2 绑定库存 + buff clamp | ✅ 地基牢固 | R-P2-2 迁移事务、R-P2-3 clamp 下限 |
| M2 道途/转修 | ✅ | R-P2-1 宗师成本口径 |
| M3 飞升点 | ✅ 红线 + 来源 + 冷却齐备 | — |
| M4 活动 + 宗门战 | ✅ 宗门战接战斗与结算、活动商店就绪 | — |
| M5 坊市 | ✅ 绑定隔离红线闭合 | R-P2-6 审计仅高价查询、R-P2-7 sim 未覆盖坊市 |
