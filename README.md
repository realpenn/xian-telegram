# 问道 · 修仙 Telegram 群文字 RPG（工作标题）

一款 Chat Wars 氛围、修仙世界规格的中文 Telegram 文字 RPG。
交互采用「指令 + 按钮」，技术栈 Python + aiogram + SQLite。

## 当前状态

✅ **v0.1.5：可玩性与社交回流版**。完整设计见 **[spec.md](spec.md)**。

当前已实现 v1 主线：**注册测灵根 → 闭关攒修为 → 突破境界 → 历练 / 秘境 → 炼丹炼器 → 法宝功法配置 → 群内切磋 / 世界 Boss / 宗门**。
已接入一次性回调 token、增益丹临时 buff、世界 Boss 定时刷新与到期/击杀结算；v0.1.5 重点补足「后台一直产出、前台持续决策、群里有人情味」的可玩性层。

### v0.1.5 亮点

- 闭关变成后台被动轨，历练 / 秘境 / 炼制作为前台主动轨可并行；前台活动时间会折算闭关收益，避免产出膨胀。
- 已稳定通关的本境界地图可扫荡，仍复用战斗模拟、精力消耗和掉落口径，只免去实时等待与二次领取。
- 历练新增低频奇遇选择事件，玩家可在高风险探宝、稳妥绕行、救人得声望之间做取舍。
- 金丹 / 元婴大突破的天劫改为逐雷互动，可选择护体法宝、护盾战技、嗑大还丹或硬抗。
- 新增 `/quest` 悬赏入口，支持每日 / 周常任务、进度累加、领取奖励与长线成就；成就也会展示在 `/me`。
- 大境界突破、斩妖王、稀有掉落、天梯段位变动、宗门升级等事件会低频进入群播报 / DM 通知队列，避免刷屏同时制造回流理由。
- 任务、成就和社交播报统一走领域事件管线，并用 savepoint 隔离副作用，避免通知或任务异常回滚核心奖励。

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
