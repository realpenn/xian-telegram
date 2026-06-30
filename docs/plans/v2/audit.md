# V2 (M0–M5) 验收审计

> 基线：`uv run --with-requirements requirements.txt python -m pytest` 当前 **216 passed**。
> P0/P1 问题已修复并落测试回归（详见 git 历史）。本文件仅保留剩余 P2 待办，修复后即移除。

---

## P2 待办（低危 / DoD 缺口）

### C1. M3/M4/M5 新增产出未进 balance_sim 反套利校验
- **现象**：坊市灵石流、活动道行、飞升点均未进 `tools/balance_sim`，违反三段共同 DoD #3。
- **验收**：balance_sim 覆盖坊市/活动/飞升产出，反套利红线显式校验；化神期"最佳内容产出 < 首买成本"在含新产出后仍成立。

### C2. M0/M1 缺关键红线回归测试
- **现象**：`YUANYING_FULL_BUFF` profile 与"元婴满 buff 刷化神中/难 Boss <5%"断言未写。实测成立（0%）但无回归护栏，M2 clamp/道途调整后无人看守。
- **验收**：`tools/balance_sim` 补 `YUANYING_FULL_BUFF` profile；`tests/test_balance.py` 加"元婴圆满满 buff 打化神中/难 Boss 胜率 <5%"断言。

### C3. 文案 / 播报缺口
- **现象**：神魂劫 `need_pill` 未引导玩家去哪寻化神丹（T0.8）；M3 飞升被动升级/试炼成功无群播报、无称号解锁（T3.5）。
- **验收**：`need_pill` 文案给出化神丹来源指引（化神难图 / 太虚天门 / 残方炼丹）；飞升成功发 `game_events` 群播报并解锁称号。
