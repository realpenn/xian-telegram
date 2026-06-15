"""bot 启动：加载配置、初始化 DB、注册 Router、polling。"""
from __future__ import annotations

import logging
import os

from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.types import BotCommand
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

from handlers import (bag, boss, craft, cultivate, daily, dungeon, explore,
                      help as help_h, me, pvp, rank, sect, shop, skills, start)
from handlers.common import cleanup_callback_tokens
from models import db
from services import character, notifications, world_boss


class ActivityMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if user and not getattr(user, "is_bot", False):
            username = user.username or user.full_name or str(user.id)
            await character.touch_activity(user.id, username)
        return await handler(event, data)

_COMMANDS = [
    BotCommand(command="start", description="踏入仙途 / 测灵根"),
    BotCommand(command="me", description="查看道行"),
    BotCommand(command="cultivate", description="闭关 / 出关"),
    BotCommand(command="explore", description="历练刷怪"),
    BotCommand(command="dungeon", description="秘境副本"),
    BotCommand(command="craft", description="炼丹炼器"),
    BotCommand(command="skills", description="法宝 / 功法"),
    BotCommand(command="shop", description="NPC 商店"),
    BotCommand(command="pvp", description="群内切磋"),
    BotCommand(command="rank", description="天梯排行"),
    BotCommand(command="boss", description="世界 Boss"),
    BotCommand(command="sect", description="宗门"),
    BotCommand(command="daily", description="每日签到"),
    BotCommand(command="bag", description="储物袋"),
    BotCommand(command="help", description="指南"),
]


async def main():
    load_dotenv()
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise SystemExit("缺少 BOT_TOKEN：请复制 .env.example 为 .env 并填入 token。")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    await db.init_db()

    bot = Bot(token=token)
    scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
    scheduler.add_job(world_boss.scheduled_spawn, "cron", hour=20, minute=0, args=[bot])
    scheduler.add_job(cleanup_callback_tokens, "interval", hours=1)
    scheduler.add_job(notifications.notify_ready_actions, "interval", minutes=1, args=[bot])
    scheduler.start()
    dp = Dispatcher()
    dp.update.middleware(ActivityMiddleware())
    for module in (start, me, cultivate, explore, dungeon, craft, skills, shop, bag,
                   pvp, rank, boss, sect, daily, help_h):
        dp.include_router(module.router)

    await bot.set_my_commands(_COMMANDS)
    logging.getLogger("xian").info("问道 bot 启动，开始 polling……")
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        await db.close_db()
