# V2 (M0–M5) 验收审计

> 基线：`uv run --with-requirements requirements.txt python -m pytest` 当前 **226 passed**。
> P0 / P1 / P2 全部修复并落测试回归，无剩余待办。

## 修复里程碑
- **P0/P1（8 项）** — commit `3ddb458`：据点掉率合算、丹修/器修真实接入突破与炼器、化神丹残方配方、sect_outposts 复合主键迁移、门派战窗口/多据点、月度结算等。
- **C2 / C3 / C1** — commit `5ad9690`：
  - C2 红线回归：`YUANYING_FULL_BUFF` profile + 元婴满 buff 打化神中/难 Boss <5%；幽都裂主数值上调。
  - C3 文案/播报：神魂劫 `need_pill` 化神丹来源指引；飞升试炼/被动升级发群播报 + 派生尊号。
  - C1 反套利：balance_sim 覆盖坊市灵石流（掉落变现）/活动道行/飞升点；化神期含掉落产出 < 首买成本。
- **C4** — 低境界含掉落微套利：根因为 balance_sim 秘境口径两处 bug（漏扣 `entry_stone`、`drops` 误乘 `reward_factor`）。修正后全境界 r0–r4 反套利红线均成立（r0 5.20<6.0、r1 11.19<13.0、r4 93.92<140），未改动任何经济参数。
