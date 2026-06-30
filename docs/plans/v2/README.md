# 《问道》二期执行计划（基于 spec-v2 审查）

> 本目录是 [`spec-v2.md`](../../../spec-v2.md) 的落地执行计划。
> spec 负责"做什么 / 为什么"，本目录负责"按什么顺序、改哪些文件、验收标准是什么"。
> 实施前如需调整设计，先改 `spec-v2.md`，再据此更新本目录。

基线：当前 `feat/v2-execution-plans`，`uv run --with-requirements requirements.txt python -m pytest` **207 passed**（2026-06-30 实测）。
所有计划的总验收前提：**新增内容不破坏现存 207 个测试**。

---

## 0. 审查结论：spec-v2 的可优化点

下列结论均已对照 `main` 真实代码核对（非纸面推断）。按"必须修正 / 必须补强 / 需澄清 / 建议"分级。

### A. spec 与代码一致性（核对通过项，作为设计地基）

- `BIG_BREAKTHROUGH` 以**目标境界索引**为键（`{1:筑基,2:金丹,3:元婴}`），`big_success_rate` 读 `BIG_BREAKTHROUGH[realm+1]`。spec §9.1 写 `BIG_BREAKTHROUGH[4]=化神丹` 与之**一致** ✓。
- `next_stage` / `is_big_breakthrough` 是**数据驱动**（判据 `realm+1 < len(REALM_NAMES)`）。因此**只要往 `REALM_NAMES` 追加"化神期" + 各配置 dict 补 `[4]`**，元婴圆满会自动从 `at_cap` 翻成大突破节点、化神圆满成为新上限，无需改突破服务逻辑。这是本期最省力的接驳点。

### B. 必须修正（spec 表述与代码不符，会误导实施）

1. **"神魂劫纯复用状态机、仅改文案"不成立 —— "放开心魔"是新机制。**
   当前 `services/breakthrough.py` 的 `choose_tribulation_action` 状态机只有 `shield`/`heal_pct`/扣血，撑过 3 段即**固定**突破，**没有"奖励倍率"概念**。spec §3.3"放开心魔：若撑过本段额外提高最终奖励"需要给 `tribulation_sessions` 加字段并改结算分支。
   → **决策**：M0 二选一 —— (a) 砍掉"放开心魔"，神魂劫保持纯文案改（最省，推荐 M0 采用）；(b) 显式把状态机扩展列为任务。本目录 M0 采用 (a)，把"放开心魔"挪到 M1 作为可选增强。
   → 顺带：神魂劫要用不同选项/文案，**无需加表**——session 已存 `target_realm`，在 `_tribulation_choices()` 里按 `target_realm==4` 分流即可。

2. **"溢出修为转道行"漏写了两条结算路径，且语义不闭合。**
   `collect_seclusion`（`services/character.py:689`）与 `touch_activity` 自动收功（`services/character.py:180`）都做 `cultivation = cultivation + gained`，**均无封顶**——这正是"挂机无意义"的根因（满级修为无限涨且无去处）。
   → 实现转换必须抽**共享 helper**，两条路径都走它，否则只改一条会漏算。
   → 语义需澄清并固定（见下"需澄清"#1）。

3. **§6.3 Buff 合算上限必须落成真实 clamp 代码，不能只当 balance_sim 约定。**
   当前 `services/character.py:stats()` 里 welfare `stat_pct`、心法 `_pct`、装备 `_pct`、临时 buff 是**逐层乘算、全程无任何全局上限**。M2 道途 + M3 飞升 + M4 据点继续往上叠 → 指数膨胀；二值战斗下极易把"0% 门槛"翻成"100% 稳刷"，并**回溯打穿 M1 已调好的化神门槛**。
   → 合算上限要做成 `stats()` 管线里的**聚合 clamp 层**（按攻击向 / 生存向 / 闭关向分乘区夹顶）。这是本期最关键的架构改造，应在 M2 引入道途时落地。**跨里程碑依赖**：M2 上线后必须回归 M1 化神门槛测试。

### C. 迁移触点 spec 未列全（实施时会漏改导致 KeyError / 报告缺档）

4. `tools/balance_sim.py:report()` 有两处硬编码 `for r in range(4)`（line 172、209），`CONTENT_REALM`（line 29）缺化神易图 —— 加 realm 4 必须改，否则报告与套利校验不覆盖化神。
5. `tests/test_balance.py` 有 3 处 `range(4)` / 分档断言（line 29、157、207），需同步到 `range(5)` 或 `range(len(R.REALM_NAMES))`。
6. `config/bosses.py:_REALM_TIER`（line 49）需加 `4:"huashen"`；spec §9.1 只提"加 boss"未提选档映射，`boss_key_for_realm` 靠它选档。
7. `STAMINA_CAP / _ANCHORS / _REALM_BASE_COST / SECLUSION_STAGE_HOURS` 在 `character.py`、`me.py`、`explore.py`、`shop.py` 多处是**直接索引 `[realm]`**（非 `.get`），缺 `[4]` 会运行时 KeyError。`STAMINA_BUY_BASE` / `_REALM_TIER` 虽有 `.get` 兜底也应显式补 `[4]`。

### D. 需澄清（设计意图不闭合，实施前定稿）

1. **溢出修为转道行的精确语义**（建议取值，待评审）：
   - 满级（化神圆满）时 cultivation **封顶在 `advance_cost(4,3)`**；每次新 gain 中越过 cost 的部分 × **30%** → 道行，剩余 **70% 作为 sink 损耗**（否则 cultivation 又无限涨回，sink 失效）。
   - 元婴圆满未完成化神突破（`cultivation≥advance_cost(3,3)` 且无化神丹/未突破）：越界部分 × **15%** → 道行，作为封顶玩家过渡补偿。
   - helper 须是**纯函数 + 确定性**，便于单测：`overflow_to_daohang(realm, stage, cur_cult, gain) -> (kept_cult, daohang_gained)`。

2. **道途差异化的验收口径**：必须用**连续指标**，不能用二值胜率。
   二值战斗里 ±2~3% 的 atk/df 几乎不改单场胜负，build 差异会被抹平。但世界 Boss = chip 伤害（连续）、秘境 = 通关层比例（连续）、闭关 = 效率（连续）——道途加成在这些指标上才线性显形。M2 验收按"每条道途至少在一个连续指标上跑出可测差异"，而非"都能过同一张胜率表"（spec §4.2 末尾已有此意，计划固化为测试）。

### E. 顺序建议

- **绑定库存迁移从 M2 拆出、前置为独立小步（M2 的第 1 个任务）。** `inventory` 主键加 `bound` 是破坏性 schema 迁移，且 `add_item` 的 `ON CONFLICT(user_id,item_key)` 要同步改三键冲突（`services/character.py:434`）。单独迁移 + 测试通过后，再叠转修令 / 活动绑定物，降低 M2 体量与回滚风险。
- 其余维持 spec §11 顺序：**M0 先行，不等坊市 / 宗门战 / 道侣一起上线**。

---

## 1. 跨里程碑架构约束（所有里程碑共同遵守）

| 约束 | 来源 | 落地方式 |
|---|---|---|
| 反套利红线：新内容灵石/精力 < 当日首买成本 | spec §5.1 / §10 | 每个产出新内容都进 `tools/balance_sim` 套利校验 + `tests/test_economy.py` |
| Buff 合算上限：攻击向/生存向 ≤+25%，闭关向 ≤+60%，PvP 折半 | spec §6.3 | M2 在 `character.stats()` 落 clamp 层；M1 化神门槛预留余量 |
| 一次性 token + 原子事务：转修/突破/交易确认 | spec §1 | 复用 `callback_tokens` + `db.transaction()` |
| 领域事件播报：化神突破/道途升阶/飞升 | spec §1 | 复用 `game_events.emit_conn`（savepoint 隔离副作用） |
| 闭关并行折算：新前台动作记 `activity_windows` | spec §1 | 仿 `services/activity.record_window`，**勿**直接复用 `reserve_stamina_for_action`（它拒绝闭关中行动） |
| 存档不重置：元婴圆满直接接入 | spec §0 | 全部 schema 走 `_ensure_column` 幂等加列；旧数据回填默认值 |

---

## 2. 里程碑总览

| 里程碑 | 计划文件 | 核心交付 | 是否阻塞下一步 |
|---|---|---|---|
| **M0 满级止血** | [v2-m0-huashen-stopgap.md](v2-m0-huashen-stopgap.md) | 化神配置、化神丹+来源、化神易/中/难图、元婴→化神突破（神魂劫纯文案） | 是（其余全部依赖） |
| **M1 化神闭环** | [v2-m1-huashen-loop.md](v2-m1-huashen-loop.md) | 太虚天门、化神 Boss、化神装备/材料、化神 GEARED 平衡回归 | 否 |
| **M2 道途/转修** | [v2-m2-daotu-zhuanxiu.md](v2-m2-daotu-zhuanxiu.md) | 绑定库存迁移→五道途→道行→转修→升阶→溢出转换→**buff 合算 clamp** | 否 |
| **M3 飞升点** | [v2-m3-m5-outline.md](v2-m3-m5-outline.md#m3) | 飞升试炼、账号级被动（硬上限）、称号/播报 | 否 |
| **M4 活动与宗门战** | [v2-m3-m5-outline.md](v2-m3-m5-outline.md#m4) | 周活动副本、据点宗门战、赛季天梯 | 否 |
| **M5 玩家经济** | [v2-m3-m5-outline.md](v2-m3-m5-outline.md#m5) | 一口价坊市、交易税、审计 | 否 |

**推荐实施顺序**：M0 → M1 →（M2 绑定迁移先行）M2 → M3 → M4 → M5。M1 与 M2 可并行启动，但 M2 道途上线前 **M1 化神门槛测试必须已存在**，以便回归。
