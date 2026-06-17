"""悬赏任务与成就配置。数值初版可调。"""
from __future__ import annotations

QUESTS = {
    "daily_explore": {
        "name": "巡山斩妖",
        "period": "daily",
        "event": "explore.win",
        "target": 3,
        "reward": {"stone": 120},
    },
    "daily_craft": {
        "name": "炉火不息",
        "period": "daily",
        "event": "craft.done",
        "target": 1,
        "reward": {"stone": 80},
    },
    "daily_pvp_win": {
        "name": "一战扬名",
        "period": "daily",
        "event": "pvp.win",
        "target": 1,
        "reward": {"stone": 100},
    },
    "weekly_dungeon": {
        "name": "秘境探幽",
        "period": "weekly",
        "event": "dungeon.clear",
        "target": 3,
        "reward": {"stone": 500, "items": {"妖丹": 3}},
    },
    "weekly_boss": {
        "name": "合力诛妖",
        "period": "weekly",
        "event": "world_boss.challenge",
        "target": 5,
        "reward": {"stone": 360, "items": {"妖丹": 2}},
    },
}

ACHIEVEMENTS = {
    "first_jindan": {
        "name": "金丹初成",
        "event": "breakthrough.big_success",
        "min_target_realm": 2,
        "reward": {"stone": 300},
    },
    "first_yuanying": {
        "name": "元婴出窍",
        "event": "breakthrough.big_success",
        "min_target_realm": 3,
        "reward": {"stone": 1000},
    },
    "first_boss": {
        "name": "初斩妖王",
        "event": "explore.boss_win",
        "reward": {"stone": 160},
    },
    "first_pvp_win": {
        "name": "天梯首胜",
        "event": "pvp.win",
        "reward": {"stone": 120},
    },
    "first_dungeon_clear": {
        "name": "秘境通关",
        "event": "dungeon.clear",
        "reward": {"stone": 220},
    },
}
