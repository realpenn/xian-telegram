"""/shop —— NPC 商店与回收。"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config.items import item_name, sell_price
from config.shop import goods_for_realm, shop_price
from handlers.common import (NEED_START, action_callback_data, consume_action_callback,
                             guard_private_callback, guard_private_message, main_menu, show)
from services import character, shop

router = Router()


async def render_shop(user_id: int, now: int = None):
    char = await character.get(user_id)
    if not char:
        return NEED_START, None
    rows = []
    lines = ["🪙 NPC 商店", f"灵石：{char.spirit_stone}", "可购："]
    stamina_offer = await shop.stamina_buy_offer(user_id, now=now)
    if stamina_offer["status"] == "buy_limit":
        stamina_text = f"购买精力（今日已达上限 {stamina_offer['limit']} 次）"
    else:
        stamina_text = f"购买精力（🪙{stamina_offer['cost']} / ⚡{stamina_offer['gain']}）"
    rows.append([InlineKeyboardButton(
        text=stamina_text,
        callback_data=await action_callback_data(user_id, "shop:stamina"))])
    for key, good in goods_for_realm(char.realm):
        price = shop_price(key, char.realm)
        tag = "（炼气期半价）" if good.get("qi_half") and price < good["price"] else ""
        lines.append(f"- {item_name(key)}：{price} 灵石{tag}")
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
    if s == "stamina_ok":
        text = f"耗灵石 {res['cost']}，精力 +{res['gain']}（{res['stamina']}/{res['cap']}）。"
        if res.get("limit"):
            text += f"今日第 {res.get('nth')}/{res['limit']} 次"
            if res.get("next_cost"):
                text += f"，下次需 {res['next_cost']} 灵石"
            text += "。"
        return text
    if s == "stamina_full":
        return "精力已满，暂不必购买。"
    if s == "buy_limit":
        return f"今日买精力已达上限（{res['limit']} 次），灵石买精力非长久之计，明日再来。"
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


@router.callback_query(F.data.startswith("shop:stamina:"))
async def cb_buy_stamina(callback: CallbackQuery):
    if await guard_private_callback(callback):
        return
    if await consume_action_callback(callback) != "shop:stamina":
        return
    res = await shop.buy_stamina(callback.from_user.id)
    await show(callback, _result_text(res), main_menu())
    await callback.answer()
