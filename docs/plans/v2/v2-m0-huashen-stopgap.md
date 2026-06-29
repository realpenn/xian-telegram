# V2-M0 满级止血：开放化神期

> 对应 spec-v2 §3、§11。**唯一目标**：当前元婴圆满玩家上线后立刻有可推进的修炼目标，且化神丹有真实来源、化神图能刷。
> 阻塞关系：其余所有里程碑都依赖 M0。

## 设计定调（来自 README 审查结论）

- **神魂劫 M0 走"纯文案改 + 按 `target_realm==4` 分流选项"**，不引入"放开心魔"奖励倍率机制（挪到 M1 可选增强）。理由：当前状态机无"奖励倍率"概念，强加会扩大 M0 体量。
- M0 **不含化神装备**。化神三图验收 profile = **化神初期锚点 + 现役元婴装备/功法**（spec §3.2）。缺化神装备不阻塞 M0。
- 化神丹来源 M0 必须同步上线，否则开放上限=纸面（spec §3.4）。

---

## 任务清单

### T0.1 化神境界配置（`config/realms.py`）
- `REALM_NAMES` 追加 `"化神期"`。
- `REALM_STAGES[4] = _SUB_STAGES`（复用 初/中/后/圆满）。
- `STAMINA_CAP[4] = 240`。
- `SECLUSION_STAGE_HOURS[4] = 96`。
- `_REALM_BASE_COST[4] = 450000`（`_STAGE_MULT` 保留 1.20；如需化神更陡，单独处理，初版先 1.20）。
- `_ANCHORS[4] = ((化神初期), (化神圆满))`，按 spec §3.2：
  - 初期 `hp=24000 mp=2200 atk=1850 df=1350 spd=500 crit=175`
  - 圆满 `hp=52000 mp=4200 atk=3800 df=2800 spd=900 crit=280`
- `BIG_BREAKTHROUGH[4] = {"pill": "化神丹", "base_rate": 0.50, "tribulation": True}`。

**验收**：
- 新增 `tests/test_huashen_config.py::test_realm4_config_complete`：`len(REALM_NAMES)==5`；`REALM_STAGES[4]`、`STAMINA_CAP[4]`、`SECLUSION_STAGE_HOURS[4]`、`_REALM_BASE_COST[4]`、`_ANCHORS[4]`、`BIG_BREAKTHROUGH[4]` 均存在。
- `R.next_stage(3,3)==(4,0)` 且 `R.is_big_breakthrough(3,3) is True`；`R.next_stage(4,3) is None` 且 `R.is_big_breakthrough(4,3) is False`。
- `R.base_stats(4,0)["hp"]==24000`、`R.base_stats(4,3)["hp"]==52000`。
- **改既有断言**：`tests/test_breakthrough.py::test_realm_progression_flags` 当前断言"元婴圆满 next 为 None / 非大突破"——现在元婴圆满变为大突破节点，须把该断言改成新上限化神圆满（`next_stage(4,3) is None`）。

### T0.2 化神经济配置（`config/shop.py`）
- `STAMINA_BUY_BASE[4] = 2800`（首买 20 精力 ≈ 140 灵石/精力）。

**验收**：`tests/test_economy.py` 增 `test_huashen_stamina_buy_base`：`STAMINA_BUY_BASE[4]==2800`；`stamina_buy_cost(4,1)==2800`、`stamina_buy_cost(4,2)==5600`。

### T0.3 化神历练三图（`config/maps.py`）
按 spec §5.1 新增（键名与 spec §9.1 一致）：

| key | name | realm | difficulty | stamina | cult | 独占掉落 |
|---|---|---|---|---|---|---|
| `星陨海` | 星陨海 | 4 | 易 | 16 | 待定 | 星陨砂 |
| `幽都裂隙` | 幽都裂隙 | 4 | 中 | 18 | 待定 | 幽都魂晶 |
| `天外古墟` | 天外古墟 | 4 | 难 | 22 | 待定 | 天外残玉 / 化神丹材料 |

- 怪物/Boss 的 hp/atk/df/spd/crit 由 **T0.6 balance_sim 实跑反推**，不拍脑袋。门槛口径见 T0.6。
- `cult`（修为）明显高于元婴图（`上古战场=1000`），引导高阶玩家不回头刷低阶。
- 灵石 `stone` 区间：单位精力含妖王期望 **< 化神首买价 140 的 75%（即 < ~105）**，延续 `归墟裂谷`/`天魔古原` 的反套利写法（中/难图收益优势靠修为+独占掉落体现）。
- `天外古墟` drops 含化神丹材料（见 T0.5）。

**验收**：
- `tests/test_balance.py::TIERS` 增 `4: ("星陨海","幽都裂隙","天外古墟")`，并把 `range(4)`→`range(5)`（line 29/157/207）。
- `tests/test_economy.py`：化神三图 `map_stone_per_stamina(k) < shop.stamina_buy_cost(4,1)/20 * 0.75`。

### T0.4 化神丹道具与突破丹消耗（`config/items.py` + 复用突破服务）
- `config/items.py` 增 `化神丹`（及材料 `化神丹残方` / 化神图独占材料），定义 NPC 不直售（spec §3.4：不进 `config/shop.py:SHOP_ITEMS`）。
- 突破逻辑**零改动**：`services/breakthrough.try_advance` 已按 `BIG_BREAKTHROUGH[target]["pill"]` 取丹、缺丹返回 `need_pill`（line 121-129）。配置就位即生效。

**验收**：
- `tests/test_breakthrough.py` 增 `test_yuanying_to_huashen_needs_pill`：元婴圆满 + 修为达标 + 无化神丹 → `try_advance` 返回 `{"status":"need_pill","pill":"化神丹"}`。
- `化神丹` 不在 `SHOP_ITEMS`。

### T0.5 化神丹来源（`config/maps.py` drops + 新秘境占位）
spec §3.4 来源，M0 落地可即时上线的部分：
- 元婴难图 `天魔古原` 极低概率（weight ~1）掉 `化神丹残方` 或 `化神丹`。
- 化神易图 `星陨海` 低概率掉化神丹材料。
- 化神难图 `天外古墟` 掉化神丹材料。
- （秘境 `太虚天门` 完整丹方/材料留 M1；M0 不依赖它。）
- 世界 Boss 化神档前列材料留 M1。

**验收**：`tests/test_drops`（或并入 test_economy）断言上述 drops 表含化神丹链路 item，且权重落在 1~低位区间；元婴圆满刷 `天魔古原` 的化神丹期望 > 0 但极低（纸面校验掉率，非战斗）。

### T0.6 神魂劫（纯文案分流，`services/breakthrough.py` + `config/events.py`）
- `config/events.py` 增神魂劫选项集（spec §3.3 表，**去掉"放开心魔"**）：`凝神守一`（减伤耗法）、`祭出护体法宝`（高减伤、受装备加成）、`服大还丹`（回血回蓝、耗大还丹）。可复用现有 `TRIBULATION_ACTIONS` 字段结构（`shield`/`heal_pct`/`item`/`text`），仅文案与数值不同。
- `services/breakthrough.py:_tribulation_choices()`：按 session `target_realm` 分流——`target_realm==4` 返回神魂劫选项集，否则返回原天劫选项集。需把 `_tribulation_choices()` 改为接受 `target_realm` 参数，并在 `_tribulation_status(row)` 内透传 `row["target_realm"]`。
- 状态机其余（扣血/3 段/成功结算/`game_events` 播报）**零改动**。

**验收**：
- `tests/test_breakthrough.py` 增 `test_shenhun_tribulation_options_by_target`：构造 target_realm=4 的 session，`_tribulation_status` 返回的 `choices` 为神魂劫集；target_realm=2/3 返回原天劫集。
- `test_shenhun_full_run`：元婴圆满成功率达标→进神魂劫→3 段均选有效动作→撑过→`status=="big_success"`、`label` 含"化神期·初期"、`game_events` 落 `breakthrough.big_success`。
- `test_shenhun_fail_light_penalty`：神魂劫中途血尽 → `big_fail`、损失 30% 修为、写 `unstable_until`、**不跌境**（realm 仍为 3）。

### T0.7 balance_sim 扩展到化神（`tools/balance_sim.py`）
- `CONTENT_REALM` 增 `"星陨海": 4`。
- `report()` 两处 `for r in range(4)` → `range(len(R.REALM_NAMES))`。
- 新增/复用 profile：M0 用现有 `GEARED`（金丹/元婴满配无词条档）作为"现役元婴装备"近似；**新增 `YUANYING_FULL_BUFF`** 档（元婴圆满 + 可叠满 buff，M0 阶段先不含道途，道途留 M2 接入）。

**验收（化神门槛，离散口径）**：写入 `tests/test_balance.py`：
- **化神初期锚点 + 现役元婴装备**：`星陨海`（易）连战运行胜率稳定（接近 100%）。
- **元婴圆满满 buff（`YUANYING_FULL_BUFF`）**：可磨 `星陨海` 普通小怪（单场胜率 >0），但打 `幽都裂隙`/`天外古墟`（中/难）Boss 稳定 **< 5%**（spec §3.2 红线："不允许元婴圆满满 buff 稳定刷化神中/难 Boss"）。
- **化神中期锚点**：解锁 `幽都裂隙`（中）稳定刷；**化神后期锚点**：解锁 `天外古墟`（难）稳定刷。
- 化神三图均通过反套利校验（T0.3）。

### T0.8 UI / 文案接驳（`handlers/cultivate.py`、`handlers/me.py`、`handlers/explore.py`）
- `handlers/cultivate.py:65` 的 `at_cap` 分支：元婴圆满不再是 at_cap，自然走大突破（need_pill / 神魂劫）流程，需检查文案是否假设"已达顶峰"，改为引导玩家寻化神丹。
- `/me`、`/explore` 的境界/精力上限展示：依赖 `R.STAMINA_CAP[char.realm]` 直接索引——T0.1 补 `[4]` 后自动可用，确认无其它 `range(4)` 式硬编码。

**验收**：手动/集成测试 `tests/test_services_flow.py` 或新增 `test_m0_flow.py`：元婴圆满玩家 → `/cultivate` 突破入口提示需化神丹（非"已封顶"）→ 持化神丹可进神魂劫。

---

## M0 完成定义（DoD）

1. `python -m pytest` 全绿（含新增化神测试，且既有 146 个不回归——注意 T0.1 须改 `test_realm_progression_flags`、T0.7 须改 `test_balance.py` 的 `range(4)`）。
2. `python -m tools.balance_sim` 报告含化神期一行，且套利校验化神档显示 ✅堵住。
3. 一个元婴圆满存档：能看到化神突破目标 → 通过化神图/天魔古原拿到化神丹 → 神魂劫 → 进化神初期 → 化神易图可刷。
4. 无破坏性 schema 改动（M0 不动表结构，纯配置 + 突破分流）。

## 风险与回避

| 风险 | 回避 |
|---|---|
| 加 `REALM_NAMES[4]` 但化神丹无来源 → 玩家撞 `need_pill` 死路 | T0.4/T0.5 与 T0.1 **同一批次上线**，DoD #3 端到端校验 |
| 二值战斗下化神门槛要么全输要么全赢、过渡带窄 | 用 T0.7 离散口径（易可刷 / 中难 Boss <5%）而非"偶尔输赢"调参 |
| 漏改 `test_realm_progression_flags` 导致既有测试红 | T0.1 验收显式列出该改动 |
