"""交互层共用组件：主菜单、进度条、消息编辑（回调幂等）。"""
from __future__ import annotations

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

NEED_START = "道友尚未踏入仙途，请先发送 /start 测灵根、开启修行。"
PRIVATE_ONLY = "养成诸事请移步私聊。群中暂且只留切磋、排行与宗门播报。"


def is_private_chat(chat) -> bool:
    chat_type = str(getattr(chat, "type", "")).lower()
    return chat_type == "private" or chat_type.endswith(".private")


async def guard_private_message(message) -> bool:
    if is_private_chat(message.chat):
        return False
    await message.answer(PRIVATE_ONLY)
    return True


async def guard_private_callback(callback) -> bool:
    if callback.message and is_private_chat(callback.message.chat):
        return False
    await callback.answer(PRIVATE_ONLY, show_alert=True)
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


def menu_with_breakthrough(can_advance: bool) -> InlineKeyboardMarkup:
    rows = []
    if can_advance:
        rows.append([InlineKeyboardButton(text="⚡ 尝试突破", callback_data="bt:do")])
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
