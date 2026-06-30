# V2 (M0–M5) 验收审计

> 基线：`uv run --with-requirements requirements.txt python -m pytest` 当前 **225 passed**。
> P0/P1 及 P2(C1–C3) 已修复并落测试回归（详见 git 历史）。本文件仅保留 C1 反套利校验中新发现的低境界观测项，决策后即移除。

---

## P2 观测（C1 反套利校验中新发现）

### C4. 低境界(r0/r1)含掉落变现后微套利
- **现象**：`balance_sim.best_content_value_per_stamina`（灵石+掉落 sell 口径，对应坊市灵石流）下，r0≈6.3 > 首买 6.0、r1≈15.3 > 首买 13.0，略超反套利红线。原仅算灵石口径时堵住（`test_buy_stamina_costlier_than_best_content_yield` 仍绿）。
- **实际影响**：极小——首买为当日第 1 次（第 2/3 次翻倍至 240/480）、`STAMINA_BUY_DAILY_LIMIT=3` 封顶、炼气/筑基期灵石稀缺且快速升级，几乎无可观套利空间。
- **验收**：化神期（C1 核心目标）已 ✅堵住（r4 含掉落 ≈126 < 首买 140，元婴 r2/结丹 r3 同样堵住）。低境界是否调参（微调低图材料 sell 或 `STAMINA_BUY_BASE[0/1]`）待产品决策；本条为诚实记录，非 M0–M5 验收 blocker。
