"""/shop —— NPC 商店与回收。"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config.items import item_name, sell_price
from config.shop import goods_for_realm
from handlers.common import (NEED_START, action_callback_data, consume_action_callback,
                             guard_private_callback, guard_private_message, main_menu, show)
from services import character, shop

router = Router()


async def render_shop(user_id: int):
    char = await character.get(user_id)
    if not char:
        return NEED_START, None
    rows = []
    lines = ["🪙 NPC 商店", f"灵石：{char.spirit_stone}", "可购："]
    for key, good in goods_for_realm(char.realm):
        lines.append(f"- {item_name(key)}：{good['price']} 灵石")
        rows.append([InlineKeyboardButton(
            text=f"买 {item_name(key)}",
            callback_data=await action_callback_data(user_id, f"shop:buy:{key}"))])
    inv = await character.inventory(user_id)
    sellable = [(key, qty) for key, qty in inv if sell_price(key) > 0]
    if sellable:
        lines.append("可回收：")
        for key, qty in sellable:
            lines.append(f"- {item_name(key)}×{qty}：{sell_price(key)} 灵石/个")
            rows.append([InlineKeyboardButton(
                text=f"卖 {item_name(key)}",
                callback_data=await action_callback_data(user_id, f"shop:sell:{key}"))])
    rows += main_menu().inline_keyboard
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


def _result_text(res: dict) -> str:
    s = res["status"]
    if s == "ok" and "cost" in res:
        return f"购得 {res['item']}×{res['qty']}，耗灵石 {res['cost']}。"
    if s == "ok":
        return f"回收 {res['item']}×{res['qty']}，得灵石 {res['gain']}。"
    if s == "no_stone":
        return f"灵石不足（需 {res['need']}，余 {res['have']}）。"
    if s == "no_item":
        return f"储物袋中 {res['item']} 不足，现有 {res['have']}。"
    if s == "locked":
        return "境界未至，店主暂不售此物。"
    if s == "missing":
        return NEED_START
    return "店主摇头，此物暂不可交易。"


@router.message(Command("shop"))
async def cmd_shop(message: Message):
    if await guard_private_message(message):
        return
    text, markup = await render_shop(message.from_user.id)
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "nav:shop")
async def cb_shop(callback: CallbackQuery):
    if await guard_private_callback(callback):
        return
    text, markup = await render_shop(callback.from_user.id)
    await show(callback, text, markup)
    await callback.answer()


@router.callback_query(F.data.startswith("shop:buy:"))
async def cb_buy(callback: CallbackQuery):
    if await guard_private_callback(callback):
        return
    action = await consume_action_callback(callback)
    if not action or not action.startswith("shop:buy:"):
        return
    res = await shop.buy(callback.from_user.id, action.split(":", 2)[2])
    await show(callback, _result_text(res), main_menu())
    await callback.answer()


@router.callback_query(F.data.startswith("shop:sell:"))
async def cb_sell(callback: CallbackQuery):
    if await guard_private_callback(callback):
        return
    action = await consume_action_callback(callback)
    if not action or not action.startswith("shop:sell:"):
        return
    res = await shop.sell(callback.from_user.id, action.split(":", 2)[2])
    await show(callback, _result_text(res), main_menu())
    await callback.answer()
