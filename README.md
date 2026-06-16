# 问道 · 修仙 Telegram 群文字 RPG（工作标题）

一款 Chat Wars 氛围、修仙世界规格的中文 Telegram 文字 RPG。
交互采用「指令 + 按钮」，技术栈 Python + aiogram + SQLite。

## 当前状态

✅ **v0.1.4：气血法力与历练扩展版**。完整设计见 **[spec.md](spec.md)**。

当前已实现 v1 主线：**注册测灵根 → 闭关攒修为 → 突破境界 → 历练 / 秘境 → 炼丹炼器 → 法宝功法配置 → 群内切磋 / 世界 Boss / 宗门**。
已接入一次性回调 token、增益丹临时 buff、世界 Boss 定时刷新与到期/击杀结算；v0.1.4 重点把气血 / 法力做成跨活动资源，并扩展历练地图难度与小群 Boss 体验。

### v0.1.4 亮点

- 气血 / 法力会在历练与秘境之间保留，并随时间自然恢复；战败有重伤地板，不会损失修为或装备。
- 疗伤丹 / 补灵丹 / 大还丹改为恢复气血、法力或双资源；补灵丹不再恢复精力，买精力继续走商店每日限制与递增价格。
- 每个大境界新增易 / 中 / 难三档历练地图，当前境界地图默认展示，低阶地图折叠用于补材料；困难图加入独占材料。
- 历练开局锁定遭遇计划、时长和出发血蓝，结算展示战斗前后气血 / 法力，避免晚领或中途服丹改写战斗结果。
- 世界 Boss 会记录群内已知修仙者，按中位境界选档并按人数缩放血量，定时刷新消息也带挑战 / 查看按钮。
- 数据库迁移兼容旧角色和在途历练 / 秘境，新增气血法力、历练计划、Boss 群成员记录等回归测试。

欢迎道友以 **Issue / Pull Request** 讨论。

## 运行

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # 填入向 @BotFather 申请的 BOT_TOKEN
python -m bot                 # 启动 bot（polling）
```

在 Telegram 私聊里发送 `/start` 测灵根，再用 `/cultivate`、`/explore`、`/dungeon`、`/craft`、`/skills`、`/shop` 等指令养成；在群里使用 `/pvp`、`/rank`、`/boss`，用 `/sect` 处理宗门事务。
玩家向详细说明见 **[问道玩家指南](docs/USER_GUIDE.md)**。
开发自检：`python -m pytest`（战斗 / 结算 / 突破 / 制造 / 秘境 / 经济 / PvP / Boss / 宗门核心逻辑单测）。

## v1 范围

个人养成核心循环（闭关修炼 → 突破境界 → 历练刷怪 → 炼丹炼器 → 变强）
+ PvE（历练 / 秘境 / 妖王 / 世界 Boss）
+ PvP 群多人玩法（切磋 / 天梯 / 宗门）。

境界跨度：炼气 → 筑基 → 金丹 → 元婴。

## 技术栈

- Python + [aiogram](https://github.com/aiogram/aiogram) 3.x
- SQLite（aiosqlite）
- APScheduler（定时事件）

设计细节、数值公式、数据模型与实施拆分，详见 **[spec.md](spec.md)**。
