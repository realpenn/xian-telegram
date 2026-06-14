# 问道 · 修仙 Telegram 群文字 RPG（工作标题）

一款 Chat Wars 氛围、修仙世界规格的中文 Telegram 文字 RPG。
交互采用「指令 + 按钮」，技术栈 Python + aiogram + SQLite。

## 当前状态

🚧 **v1 spec polish 中**（按 M1/M2/M3 stacked PR 拆分）。完整设计见 **[spec.md](spec.md)**。

当前已实现 v1 主线：**注册测灵根 → 闭关攒修为 → 突破境界 → 历练 / 秘境 → 炼丹炼器 → 法宝功法配置 → 群内切磋 / 世界 Boss / 宗门**。
已接入一次性回调 token、世界 Boss 定时刷新与到期/击杀结算；后续主要继续打磨数值与真机体验。

欢迎道友以 **Issue / Pull Request** 讨论。

## 运行

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # 填入向 @BotFather 申请的 BOT_TOKEN
python -m bot                 # 启动 bot（polling）
```

在 Telegram 私聊里发送 `/start` 测灵根，再用 `/cultivate`、`/explore`、`/dungeon`、`/craft`、`/skills`、`/shop` 等指令养成；在群里使用 `/pvp`、`/rank`、`/boss`，用 `/sect` 处理宗门事务。
开发自检：`pytest`（战斗 / 结算 / 突破 / 制造 / 秘境 / 经济 / PvP / Boss / 宗门核心逻辑单测）。

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
