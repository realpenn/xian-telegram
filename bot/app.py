"""bot 启动：加载配置、初始化 DB、注册 Router、polling。"""
from __future__ import annotations

import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from dotenv import load_dotenv

from handlers import (bag, boss, craft, cultivate, daily, dungeon, explore,
                      help as help_h, me, pvp, rank, sect, shop, skills, start)
from models import db

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
    dp = Dispatcher()
    for module in (start, me, cultivate, explore, dungeon, craft, skills, shop, bag,
                   pvp, rank, boss, sect, daily, help_h):
        dp.include_router(module.router)

    await bot.set_my_commands(_COMMANDS)
    logging.getLogger("xian").info("问道 bot 启动，开始 polling……")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await db.close_db()
