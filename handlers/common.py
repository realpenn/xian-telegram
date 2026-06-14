"""交互层共用组件：主菜单、进度条、消息编辑（回调幂等）。"""
from __future__ import annotations

import secrets
import time
from typing import Optional

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from models import db

NEED_START = "道友尚未踏入仙途，请先发送 /start 测灵根、开启修行。"
PRIVATE_ONLY = "养成诸事请移步私聊。群中暂且只留切磋、排行与宗门播报。"
TOKEN_TTL_SECONDS = 15 * 60
TOKEN_EXPIRED = "此操作已过期或已处理，请刷新页面后再试。"


async def dm_link(bot) -> str:
    me = await bot.get_me()
    if me.username:
        return f"https://t.me/{me.username}?start=menu"
    return ""


def is_private_chat(chat) -> bool:
    chat_type = str(getattr(chat, "type", "")).lower()
    return chat_type == "private" or chat_type.endswith(".private")


async def action_callback_data(user_id: Optional[int], action: str) -> str:
    token = secrets.token_urlsafe(6)
    now = int(time.time())
    await db.execute(
        "INSERT INTO callback_tokens(token, user_id, action, created_at) VALUES(?,?,?,?)",
        (token, user_id, action, now))
    return f"{action}:{token}"


async def consume_action_callback(callback):
    if not callback.data or ":" not in callback.data:
        await callback.answer(TOKEN_EXPIRED, show_alert=True)
        return None
    action, token = callback.data.rsplit(":", 1)
    now = int(time.time())
    async with db.transaction() as conn:
        cur = await conn.execute("SELECT * FROM callback_tokens WHERE token=?", (token,))
        row = await cur.fetchone()
        await cur.close()
        if (not row or row["action"] != action or row["consumed_at"] is not None
                or now - row["created_at"] > TOKEN_TTL_SECONDS
                or (row["user_id"] is not None and row["user_id"] != callback.from_user.id)):
            await callback.answer(TOKEN_EXPIRED, show_alert=True)
            return None
        await conn.execute(
            "UPDATE callback_tokens SET consumed_at=? WHERE token=?",
            (now, token))
    return action


async def cleanup_callback_tokens(now: int = None):
    """清理已消费或已过期的一次性回调 token，避免该表无限增长。"""
    now = int(time.time()) if now is None else now
    await db.execute(
        "DELETE FROM callback_tokens WHERE consumed_at IS NOT NULL OR created_at < ?",
        (now - TOKEN_TTL_SECONDS,))


async def guard_private_message(message) -> bool:
    if is_private_chat(message.chat):
        return False
    link = await dm_link(message.bot)
    await message.answer(PRIVATE_ONLY + (f"\n私聊入口：{link}" if link else ""))
    return True


async def guard_private_callback(callback) -> bool:
    if callback.message and is_private_chat(callback.message.chat):
        return False
    link = await dm_link(callback.bot)
    await callback.answer(PRIVATE_ONLY + (f"\n{link}" if link else ""), show_alert=True)
    return True


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📈 道行", callback_data="nav:me"),
         InlineKeyboardButton(text="🧘 闭关", callback_data="nav:cultivate")],
        [InlineKeyboardButton(text="⚔️ 历练", callback_data="nav:explore"),
         InlineKeyboardButton(text="🏯 秘境", callback_data="nav:dungeon")],
        [InlineKeyboardButton(text="💊 炼制", callback_data="nav:craft"),
         InlineKeyboardButton(text="📖 功法", callback_data="nav:skills")],
        [InlineKeyboardButton(text="🪙 商店", callback_data="nav:shop"),
         InlineKeyboardButton(text="🎒 储物袋", callback_data="nav:bag")],
        [InlineKeyboardButton(text="⛩️ 宗门", callback_data="nav:sect")],
        [InlineKeyboardButton(text="📖 指南", callback_data="nav:help")],
    ])


async def menu_with_breakthrough(user_id: int, can_advance: bool) -> InlineKeyboardMarkup:
    rows = []
    if can_advance:
        rows.append([InlineKeyboardButton(
            text="⚡ 尝试突破",
            callback_data=await action_callback_data(user_id, "bt:do"))])
    rows += main_menu().inline_keyboard
    return InlineKeyboardMarkup(inline_keyboard=rows)


def progress_bar(cur: int, total: int, width: int = 10) -> str:
    if total <= 0:
        return "▰" * width
    filled = max(0, min(width, int(width * cur / total)))
    return "▰" * filled + "▱" * (width - filled)


async def show(callback, text: str, markup=None):
    """编辑回调消息；内容未变则静默，不可编辑则补发。"""
    try:
        await callback.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest as e:
        if "not modified" in str(e).lower():
            return
        await callback.message.answer(text, reply_markup=markup)
