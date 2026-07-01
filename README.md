# 问道 · 修仙 Telegram 群文字 RPG

一款 Chat Wars 氛围、修仙世界规格的中文 Telegram 文字 RPG。交互采用「指令 + 按钮」，技术栈为 Python + aiogram + SQLite。

## 当前状态

当前 `main` 已从 v1 主线推进到 v2 实现态：**境界开放到化神圆满**，并接入道途 / 转修、飞升点、周活动、宗门战据点和玩家一口价坊市。

完整设计与执行拆分见 [spec.md](spec.md)、[spec-v2.md](spec-v2.md) 和 [docs/plans/v2](docs/plans/v2)。玩家基础玩法说明见 [问道玩家指南](docs/USER_GUIDE.md)。

## 已实现玩法

- 个人成长：注册测灵根、角色面板、闭关 / 自动闭关、修为溢出分流、大小境界突破、金丹起交互式天劫、元婴到化神的神魂劫。
- PvE：每境界三档历练地图、低阶地图折叠、稳定通关后的扫荡、低频奇遇选择、秘境逐层挑战、世界 Boss 分档与群内合击。
- 资源与战斗：精力、气血、法力均按时间惰性恢复；历练 / 秘境按出发血蓝快照结算，重伤不丢装备和修为。
- 炼制与装备：炼丹、炼器、丹方 / 图纸解锁、法宝装备、强化、重铸、分解器魂，高阶化神装备和化神丹炼制链路已接入。
- 长线成长：元婴起选择五类道途（剑修、体修、丹修、器修、符阵），支持道行升阶、转修令切换主道途；化神圆满后溢出修为可转为道行与飞升点。
- 群玩法：群内切磋、天梯积分 / 声望、周榜结算、宗门创建 / 加入 / 捐输 / 任务 / 商店 / 升级、宗门战据点与赛季结算。
- 周期内容：每日签到、悬赏任务 / 成就、周活动副本、活动商店、月赛季称号与道行奖励。
- 玩家经济：NPC 商店与回收、玩家一口价坊市、成交税、绑定库存隔离；化神丹、转修令、保命符等关键物品不可上架。
- 通知与安全：一次性回调 token、DB 写事务串行化、WAL 读写隔离、定时 Boss 刷新与结算、完成提醒、低频社交播报。

境界跨度：

```text
炼气期 → 筑基期 → 金丹期 → 元婴期 → 化神期
```

## 指令速览

私聊养成入口：

```text
/start        踏入仙途 / 测灵根
/me           查看角色面板
/cultivate    闭关 / 出关
/explore      历练
/dungeon      秘境
/craft        炼丹炼器
/skills       法宝 / 功法
/shop         NPC 商店
/daily        每日签到
/quest        悬赏任务
/bag          储物袋
/path         道途 / 转修
/ascension    飞升试炼与被动
/weekly       周活动副本
/market       玩家坊市
/sectwar      宗门战据点
/help         指南
```

群聊与社交入口：

```text
/pvp          群内切磋 / 天梯
/rank         天梯排行
/boss         群内世界 Boss
/sect         宗门事务
```

## 运行

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # 填入向 @BotFather 申请的 BOT_TOKEN
python -m bot                 # 启动 bot（polling）
```

SQLite 数据库会自动创建在 `data/xian.db`。也可以用 `python main.py` 启动，等价于 `python -m bot`。

## 开发自检

```bash
python -m pytest
python -m tools.balance_sim
```

测试覆盖战斗、结算、突破、气血法力、炼制、秘境、经济、PvP、世界 Boss、宗门、道途、飞升、周活动、坊市、读写隔离和 v2 审计回归。

## 技术栈

- Python + [aiogram](https://github.com/aiogram/aiogram) 3.x
- SQLite + aiosqlite（WAL、独立只读连接、写事务串行化）
- APScheduler（世界 Boss、PvP / 宗门战 / 月赛季结算、通知与清理任务）
