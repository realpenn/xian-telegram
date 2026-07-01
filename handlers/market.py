"""/market —— 玩家一口价坊市。"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config.items import is_tradable, item_name
from handlers.common import (NEED_START, action_callback_data, consume_action_callback,
                             guard_private_callback, guard_private_message, main_menu, show)
from services import character, market

router = Router()
DEFAULT_LIST_PRICE = 100
LIST_PRICE_STEP = 100
MIN_LIST_PRICE = 100
MAX_LIST_PRICE = 10_000_000


async def render_market(user_id: int):
    char = await character.get(user_id)
    if not char:
        return NEED_START, None
    listings = await market.list_active()
    inv = [(k, q) for k, q in await character.inventory(user_id, bound=0) if is_tradable(k)]
    lines = ["🏷️ 坊市", f"🪙 灵石 {char.spirit_stone}", "—— 在售 ——"]
    rows = []
    if listings:
        for row in listings[:10]:
            lines.append(f"#{row['id']} {row['item']}×{row['qty']}：{row['price']} 灵石")
            if row["seller_id"] == user_id:
                rows.append([InlineKeyboardButton(
                    text=f"撤单 #{row['id']}",
                    callback_data=await action_callback_data(user_id, f"market:cancel:{row['id']}"))])
            else:
                rows.append([InlineKeyboardButton(
                    text=f"购买 #{row['id']}",
                    callback_data=await action_callback_data(user_id, f"market:buy:{row['id']}"))])
    else:
        lines.append("暂无挂单。")
    if inv:
        lines.append("—— 上架（点物品后可 +/-100 调价，绑定物不可上架）——")
        for key, qty in inv[:8]:
            lines.append(f"{item_name(key)} ×{qty}")
            rows.append([InlineKeyboardButton(
                text=f"上架 {item_name(key)}",
                callback_data=await action_callback_data(user_id, f"market:list:{key}"))])
    else:
        lines.append("无可上架的非绑定物品。")
    rows += main_menu().inline_keyboard
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


def _clamp_price(price: int) -> int:
    return max(MIN_LIST_PRICE, min(MAX_LIST_PRICE, int(price)))


async def render_price_editor(user_id: int, key: str, price: int):
    """定价视图：默认 100，可反复 +/-100 后确认上架。"""
    price = _clamp_price(price)
    tax = int(price * market.MARKET_TAX_RATE)
    lines = [
        f"🏷️ 上架 {item_name(key)} ×1",
        f"单价：{price} 灵石",
        f"成交税 {int(market.MARKET_TAX_RATE * 100)}%，卖出实得 {price - tax} 灵石",
    ]
    rows = [
        [InlineKeyboardButton(
            text="➖ 100",
            callback_data=await action_callback_data(user_id, f"market:price:{key}:{price - LIST_PRICE_STEP}")),
         InlineKeyboardButton(
            text="➕ 100",
            callback_data=await action_callback_data(user_id, f"market:price:{key}:{price + LIST_PRICE_STEP}"))],
        [InlineKeyboardButton(
            text=f"✅ 确认上架（{price} 灵石）",
            callback_data=await action_callback_data(user_id, f"market:confirm:{key}:{price}"))],
        [InlineKeyboardButton(
            text="↩️ 返回坊市",
            callback_data=await action_callback_data(user_id, "market:back:"))],
    ]
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


def _result_text(res: dict) -> str:
    s = res["status"]
    if s == "ok" and "listing_id" in res:
        return f"已上架 #{res['listing_id']}：{res['item']}×{res['qty']}，价格 {res['price']} 灵石。"
    if s == "ok" and "seller_gain" in res:
        return f"购得 {res['item']}×{res['qty']}，支付 {res['price']} 灵石（税 {res['tax']}）。"
    if s == "ok":
        return f"已撤下 {res['item']}×{res['qty']}，物品返还储物袋。"
    if s == "no_trade":
        return f"{res['item']} 为绑定/限售物品，不可在坊市交易。"
    if s == "no_item":
        return f"非绑定物品不足（现有 {res['have']}）。"
    if s == "no_stone":
        return f"灵石不足（需 {res['need']}，现有 {res['have']}）。"
    if s == "not_available":
        return "该挂单已不可购买或撤回。"
    if s == "self_buy":
        return "不可购买自己的挂单。"
    if s == "forbidden":
        return "不可撤回他人挂单。"
    if s == "bad_request":
        return "上架参数不合规。"
    if s == "missing":
        return NEED_START
    return "坊市操作未成。"


@router.message(Command("market"))
async def cmd_market(message: Message):
    if await guard_private_message(message):
        return
    text, markup = await render_market(message.from_user.id)
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "nav:market")
async def cb_market(callback: CallbackQuery):
    if await guard_private_callback(callback):
        return
    text, markup = await render_market(callback.from_user.id)
    await show(callback, text, markup)
    await callback.answer()


@router.callback_query(F.data.startswith("market:"))
async def cb_market_action(callback: CallbackQuery):
    if await guard_private_callback(callback):
        return
    action = await consume_action_callback(callback)
    if not action or not action.startswith("market:"):
        return
    parts = action.split(":", 2)
    op, value = parts[1], parts[2]
    uid = callback.from_user.id
    # 上架走定价编辑器：list=打开（默认 100），price=调价重绘，confirm=真正上架。
    if op == "list":
        text, markup = await render_price_editor(uid, value, DEFAULT_LIST_PRICE)
        await show(callback, text, markup)
        await callback.answer()
        return
    if op == "price":
        key, price = value.rsplit(":", 1)
        text, markup = await render_price_editor(uid, key, int(price))
        await show(callback, text, markup)
        await callback.answer()
        return
    if op == "back":
        text, markup = await render_market(uid)
        await show(callback, text, markup)
        await callback.answer()
        return
    if op == "confirm":
        key, price = value.rsplit(":", 1)
        res = await market.create_listing(uid, key, 1, _clamp_price(int(price)))
    elif op == "buy":
        res = await market.buy(uid, int(value))
    else:
        res = await market.cancel(uid, int(value))
    await show(callback, _result_text(res), main_menu())
    await callback.answer()
