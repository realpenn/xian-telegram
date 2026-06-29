# V2-M2 道途 / 转修：元婴起的专修长线 + Buff 合算 clamp

> 对应 spec-v2 §4、§6.3、§7.2、§9。
> 目标：元婴期起形成职业差异（build 多样性），封顶后仍能积累道行；并落地**全局 buff 合算上限**（本期最关键架构改造）。
> 前置：M0 已上线。**任务严格按下列顺序**——先绑定迁移，再 clamp 层，再道途内容。

---

## 设计定调（来自 README 审查结论）

- **绑定库存迁移从 spec 的 M2 内部拆为"M2 第 1 任务"独立先行**（审查结论 E）：破坏性 schema + `add_item` 冲突子句改动，先单独迁移测试通过，再叠道途物品。
- **§6.3 合算上限做成 `character.stats()` 里的真实 clamp 层**（审查结论 B-3），不是 balance_sim 约定。否则道途+飞升+据点逐层乘算会指数膨胀并回溯打穿 M1 化神门槛。
- **道途差异化用连续指标验收**（审查结论 D-2）：Boss chip 伤害 / 秘境通关层比例 / 闭关效率，不用二值胜率。
- 溢出修为转道行抽**共享纯函数 helper**，两条结算路径都走它（审查结论 B-2 + D-1）。

---

## 任务清单（按依赖顺序）

### T2.1 最小绑定库存迁移（独立先行）（`models/db.py`、`services/character.py`）
- `inventory` 主键改为 `(user_id, item_key, bound)`（spec §7.2 方案 1）。因 `_ensure_column` 无法改主键，需**新建表 + 迁移**：
  - 启动迁移：若旧 `inventory` 无 `bound` 列 → 建新表 `inventory_new(user_id,item_key,bound DEFAULT 0,qty,PRIMARY KEY(user_id,item_key,bound))` → `INSERT ... SELECT ...,0,qty` → 原子 rename。放进 `init_db` 的迁移段，幂等可重入。
- `services/character.py:add_item`（line 432-436）的 `ON CONFLICT(user_id, item_key)` → `ON CONFLICT(user_id, item_key, bound)`，并给 `add_item` / `item_qty` / `inventory` / `_grant_reward_conn` 增加 `bound` 参数（默认 0，保持旧调用兼容）。
- 突破/天劫取丹（`services/breakthrough.py` 的 `SELECT qty FROM inventory WHERE user_id=? AND item_key=?`）：需决定丹药取绑定还是非绑定优先；初版**合并读取**（`SUM(qty)`）+ 扣减优先扣绑定，避免回归。
- M2 阶段服务层**只暴露绑定物增减/读取，不开放交易 UI**（坊市留 M5，spec §7.1）。

**验收**（`tests/test_db_isolation.py` / 新 `test_inventory_bound.py`）：
- 旧存档迁移后所有物品 `bound=0`，qty 不变。
- 同玩家可同时持 `(item,bound=0)` 与 `(item,bound=1)` 两行。
- `add_item` 默认行为与迁移前一致（旧测试不回归）。
- 突破取丹在绑定/非绑定混合库存下仍正确扣减。

### T2.2 Buff 合算上限 clamp 层（`config/realms.py` 或新 `config/buffs.py` + `services/character.py:stats`）
spec §6.3。当前 `stats()` 逐层乘算无上限，须加聚合 clamp：
- 定义乘区与上限常量：
  - 攻击向（atk/crit 相关）合算 ≤ **+25%**
  - 生存向（hp/df/减伤）合算 ≤ **+25%**
  - 闭关/道行效率向（`seclusion_pct` 等）合算 ≤ **+60%**
- 重构 `stats()`：把各来源的百分比加成**先按乘区累加，clamp，再统一应用**，而非现在的"逐 buff 立即乘"。需覆盖 welfare `stat_pct`、心法 `_pct`、装备 `_pct`、临时 buff、（M2 起）道途、（M3 起）飞升、（M4 起）据点。
- PvP 路径：所有道途/飞升/据点百分比**默认折半**并单独维护上限（`services/pvp.py` 取属性处传 `pvp=True` 走折半分支）。
- 闭关效率 clamp：`place_factor` 的合算在 `collect_seclusion`/`touch_activity` 处夹 +60%。

**验收**（新 `tests/test_buff_caps.py`）：
- 构造攻击向叠加超 +25% 的来源组合 → `stats()` 实际 atk 提升被夹在 +25%。
- 生存向、闭关向同理夹顶。
- PvP 取属性时道途/飞升加成折半。
- **回归**：重跑 M1 化神门槛测试（`test_balance.py`），确认 clamp 后化神门槛不被打穿、也未被误伤变得打不过。

### T2.3 道途数据表与配置（`models/db.py`、新 `config/dao_paths.py`、新 `services/dao_path.py`）
- 建表（spec §9.2，走 `_ensure_column`/建表幂等）：`dao_paths(user_id,path_key,xp,rank,active,unlocked_at, PK(user_id,path_key))`、`path_events(...)`。
- `config/dao_paths.py`：五道途（剑修/体修/丹修/器修/符阵）的定位、各 rank（入门/小成/大成/圆满/宗师）加成方向与数值。加成**入门 2~3% 量级**（spec §4.2）。
- `services/dao_path.py`：解锁（元婴初期起，首条免费）、读取激活道途、加成查询（供 T2.2 clamp 层消费）。

**验收**（新 `tests/test_dao_path.py`）：
- 元婴初期可解锁首条道途（免费）；元婴初期以下不可。
- 五道途各 rank 加成数值符合 spec §4.2 方向与量级。
- 道途加成接入 T2.2 clamp 后仍受合算上限约束。

### T2.4 道行资源与溢出修为转换（`services/character.py` + `services/dao_path.py`）
- 道行存储：新增 `characters.daohang` 列（`_ensure_column`）或并入道途表；初版建议独立列，便于读取。
- **共享纯函数**（审查结论 B-2/D-1）`settle.overflow_to_daohang(realm, stage, cur_cult, gain) -> (kept_cult, daohang)`：
  - 化神圆满（realm=4,stage=3）：cultivation 封顶 `advance_cost(4,3)`；越界 gain × **30%** → 道行，其余损耗。
  - 元婴圆满未完成化神突破（realm=3,stage=3 且 cur≥`advance_cost(3,3)`）：越界 gain × **15%** → 道行。
  - 其它情况：`kept_cult=cur+gain, daohang=0`（不变）。
- **两条结算路径都改**：`collect_seclusion`（character.py:689）与 `touch_activity` 自动收功（character.py:180）把 `cultivation = cultivation + gained` 换成调用该 helper，并把 daohang 落库 + 写 `path_events`。
- 道行其它来源（spec §4.3）：历练/秘境/Boss/炼制/宗门/PvP 周榜给少量道行（在各结算处加少量 `daohang` 发放）。
- 道行不可交易、不可夺取（不进任何交易/PvP 掠夺路径）。

**验收**（新 `tests/test_daohang.py`）：
- `overflow_to_daohang` 纯函数确定性单测：化神圆满 gain=1000 → kept=cost、daohang=300；元婴圆满 gain=1000 → daohang=150；非满级 → daohang=0、cult 正常累加。
- `collect_seclusion` 在化神圆满满修为时：cultivation 不再无限涨，daohang 增长、写 `path_events`。
- `touch_activity` 自动收功路径同样转换（**防只改一条**）。

### T2.5 道途升阶（`services/dao_path.py` + `handlers/me.py` 或新 `handlers/path.py`）
- 升阶成本（spec §4.3 表）：入门免费 / 小成低额道行 / 大成中额道行+材料 / 圆满高额+活动秘境材料 / 宗师周期性飞升点（飞升点 M3 才有，宗师档可留接口 M3 接通）。
- 升阶走 `db.transaction()` + `callback_tokens` 一次性确认。
- 升阶成功发 `game_events`（道途升阶播报，spec §1）。

**验收**：`test_dao_path.py`：道行足额可升阶、扣道行+材料、写 `path_events`、发领域事件；道行不足返回 need。

### T2.6 转修（`services/dao_path.py` + `handlers/path.py`）
spec §4.4：
- 多道途历史进度并存，同时仅一条 `active=1`。
- 首次选择免费；切换需 `转修令` + 灵石，冷却 7 天（存 `path_events` 或角色字段记最近转修时间）。
- 切换保留各道途等级，无经验折损。
- `转修令` 绑定语义：依赖 T2.1 绑定库存；来源化神秘境/活动商店/宗门商店，不进 NPC 直售。

**验收**（`test_dao_path.py`）：
- 转修保留各道途 rank（无折损）。
- 冷却内再转修被拒（返回剩余冷却）；缺转修令/灵石被拒。
- 转修令为绑定物（`bound=1`），不可进交易路径。

### T2.7 道途内容 sink 与连续指标验收（`tools/balance_sim.py` + `tests/test_balance.py`/`test_sinks.py`）
spec §4.2 每条道途对应内容瓶颈。**验收用连续指标，不用二值胜率**（审查结论 D-2）：
- balance_sim 新增**单条拉满道途**的 profile（剑修圆满 / 体修圆满 …），接入 T2.2 clamp。
- 剑修：化神 Boss `boss_damage_per_challenge` 显著高于体修档（chip 伤害连续可测）。
- 体修：太虚天门 `dungeon_clear_fraction`（多层无回血）显著高于剑修档。
- 丹修：突破率 / 丹药产量提升可测（非战斗指标）。
- 器修：化神法宝输出上限 / 强化成本可测。
- 符阵：闭关效率 / 道行效率提升可测（受 +60% 闭关向上限约束）。

**验收**：`test_sinks.py`/`test_balance.py`：
- 每条道途**至少一个连续指标**上跑出可测且方向正确的差异。
- 不存在"单一道途在所有玩法都最优"：任意道途在它的 sink 上领先，但在别的 sink 上不领先。
- 所有满道途档仍受 §6.3 合算上限约束（复用 T2.2 断言）。

---

## M2 完成定义（DoD）

1. `python -m pytest` 全绿，含绑定迁移、buff clamp、道途、道行、转修、连续指标 sink 测试。
2. **M1 化神门槛测试在 clamp 层 + 满道途 buff 下回归通过**（不被打穿、不被误伤）。
3. 元婴初期玩家可选道途、看到 build 差异；化神圆满玩家闭关产出转道行（挂机不再无意义）。
4. 绑定库存迁移幂等、旧档无损；转修令/活动绑定物有绑定语义，坊市仍未开放。

## 风险与回避

| 风险 | 回避 |
|---|---|
| 改主键的破坏性迁移出错 / 不可重入 | T2.1 独立先行、单独测试、迁移幂等，先于任何道途物品 |
| 道途+飞升+据点无上限指数膨胀打穿门槛 | T2.2 clamp 层先于道途内容；M1 门槛回归测试 |
| 二值战斗抹平 build 差异 → 道途沦为同一最优数值 | T2.7 用连续指标（chip 伤害/通关层/效率）验收，每道途独立 sink |
| 溢出转换只改一条结算路径 → 自动收功路径漏算 | T2.4 抽共享 helper，两条路径都改并各自加测试 |
| 转修变成"惩罚选错职业" | 保留历史进度、无折损（spec §4.4），鼓励试 build |
