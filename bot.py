"""KeyCraft Telegram token-reseller bot.

Flow (customer):
  /start -> pick region (🇧🇩 বাংলাদেশ = Bangla UI, 🌍 Global = English UI)
        -> pick a package (1B / 5B / 10B / 30B)
        -> pick a payment method (BD: bKash / Nagad / Binance Pay;
                                  Global: Binance Pay only)
        -> pay, then send TrxID, then send the Muse invite code
        -> order saved as PENDING, admin is notified
  /language -> change region / language anytime
  /cancel   -> stop the current order

Flow (admin, ADMIN_TELEGRAM_ID):
  Receives every PENDING order with Approve / Reject buttons.
  Approve -> the router buys from the CHEAPEST supplier that is in stock
             and has enough balance (auto-fallback to the next cheapest),
             then polls delivery status and notifies the customer.
  /balance  -> wallet balance + live rate per supplier
  /status   -> stock status per supplier
  /orders   -> list pending orders (with Approve / Reject buttons)
  /prices   -> show current package prices (BDT + USDT)
  /setprice -> change a package price, e.g. /setprice 1B 120
               or /setprice 5B 150 4 (BDT + USDT). Saved in the
               database, takes effect immediately, survives restarts.

Suppliers are pluggable (see suppliers/): the bot only talks to the
SupplierRouter, never to KeyCraft directly. Each supplier spends from its
OWN wallet — money is never moved between suppliers.

Run:  python bot.py        (env vars from .env, see .env.example)
"""

from __future__ import annotations

import asyncio
import logging
import re
import secrets
import sys

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

import strings
from config import Settings
from storage import OrderStore
from strings import lang_for_region, t
from suppliers import get_router, get_suppliers
from suppliers.base import SupplierError

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("keycraft-bot")

# Conversation states
REGION, PACKAGE, PAYMENT, TRXID, INVITE = range(5)

TRXID_RE = re.compile(r"^[A-Za-z0-9]{4,64}$")
INVITE_RE = re.compile(r"^[A-Za-z0-9_-]{3,32}$")

SETTINGS: Settings | None = None
STORE: OrderStore | None = None


def settings() -> Settings:
    assert SETTINGS is not None
    return SETTINGS


def store() -> OrderStore:
    assert STORE is not None
    return STORE


# ---------------------------------------------------------------------------
# Language / region helpers
# ---------------------------------------------------------------------------
def user_lang(user_id: int) -> str:
    """The user's language from their saved region ('bn' / 'en')."""
    return lang_for_region(store().get_user_region(user_id))


def admin_lang() -> str:
    """The admin's language (defaults to Bangla — the owner is Bangladeshi)."""
    region = store().get_user_region(settings().admin_telegram_id)
    return lang_for_region(region) if region else "bn"


def region_label(region: str | None) -> str:
    return strings.REGION_BUTTONS.get(region or "global", "🌍 Global")


# ---------------------------------------------------------------------------
# Keyboards
# ---------------------------------------------------------------------------
def region_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    strings.REGION_BUTTONS["bd"], callback_data="region:bd"
                )
            ],
            [
                InlineKeyboardButton(
                    strings.REGION_BUTTONS["global"],
                    callback_data="region:global",
                )
            ],
        ]
    )


def packages_keyboard(lang: str, region: str) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                strings.package_button(lang, tokens, amount, currency),
                callback_data=f"pkg:{tokens}",
            )
        ]
        for tokens, amount, currency in settings().packages_for_region(region)
    ]
    rows.append(
        [
            InlineKeyboardButton(
                t(lang, "language_button"), callback_data="change_region"
            )
        ]
    )
    return InlineKeyboardMarkup(rows)


def payment_keyboard(lang: str, region: str) -> InlineKeyboardMarkup:
    rows = []
    for method in settings().payment_methods_for_region(region):
        address = settings().payment_address(method)
        if not address:  # hide methods that are not configured
            continue
        rows.append(
            [
                InlineKeyboardButton(
                    strings.payment_method_name(lang, method),
                    callback_data=f"pay:{method}",
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton(t(lang, "back_button"), callback_data="back:packages")]
    )
    return InlineKeyboardMarkup(rows)


def admin_order_keyboard(order_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve:{order_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject:{order_id}"),
            ]
        ]
    )


# ---------------------------------------------------------------------------
# Conversation: region -> package -> payment -> trxid -> invite code
# ---------------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for /start and /language."""
    user = update.effective_user
    message = update.message
    force_region = bool(message and message.text.startswith("/language"))

    region = store().get_user_region(user.id)
    if force_region or not region:
        await message.reply_text(
            t("en", "choose_region"), reply_markup=region_keyboard()
        )
        return REGION

    lang = lang_for_region(region)
    await message.reply_text(
        t(lang, "welcome"),
        reply_markup=packages_keyboard(lang, region),
        parse_mode="Markdown",
    )
    return PACKAGE


async def region_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User picked 🇧🇩 বাংলাদেশ or 🌍 Global — save it and show packages."""
    query = update.callback_query
    await query.answer()
    region = query.data.split(":", 1)[1]
    user = update.effective_user
    store().set_user_region(user.id, region)
    lang = lang_for_region(region)

    await query.edit_message_text(
        t(lang, "region_saved_bd" if region == "bd" else "region_saved_global")
    )
    await query.message.reply_text(
        t(lang, "welcome"),
        reply_markup=packages_keyboard(lang, region),
        parse_mode="Markdown",
    )
    return PACKAGE


async def change_region(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """'🌐 Language' button in the package menu — show the region picker."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        t("en", "choose_region"), reply_markup=region_keyboard()
    )
    return REGION


async def package_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User picked a package — check live availability, then ask payment."""
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    lang = user_lang(user.id)
    region = store().get_user_region(user.id) or "global"
    tokens_b = int(query.data.split(":", 1)[1])

    priced = settings().price_for(tokens_b, region)
    if priced is None:
        await query.edit_message_text(t(lang, "error_generic"))
        return PACKAGE
    amount, currency = priced
    context.user_data["tokens_b"] = tokens_b
    context.user_data["amount"] = amount
    context.user_data["currency"] = currency
    context.user_data["region"] = region

    # Availability: is ANY supplier in stock with enough balance?
    try:
        async with get_router(settings()) as router:
            ok, reason = await router.check_availability(tokens_b)
    except SupplierError:
        ok, reason = False, "temporarily_unavailable"
    if not ok:
        await query.edit_message_text(
            t(lang, reason or "temporarily_unavailable"),
            reply_markup=packages_keyboard(lang, region),
        )
        return PACKAGE

    await query.edit_message_text(
        t(lang, "choose_payment", tokens_b=tokens_b,
          amount=strings.format_amount(lang, amount, currency)),
        reply_markup=payment_keyboard(lang, region),
        parse_mode="Markdown",
    )
    return PAYMENT


async def back_to_packages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    lang = user_lang(user.id)
    region = store().get_user_region(user.id) or "global"
    await query.edit_message_text(
        t(lang, "welcome"),
        reply_markup=packages_keyboard(lang, region),
        parse_mode="Markdown",
    )
    return PACKAGE


def new_order_id() -> str:
    return "KC-" + secrets.token_hex(4).upper()


async def payment_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User picked a payment method — show where to pay + the order ID."""
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    lang = user_lang(user.id)
    region = context.user_data.get("region") or "global"
    method = query.data.split(":", 1)[1]

    if method not in settings().payment_methods_for_region(region):
        await query.answer("Not available for your region.", show_alert=True)
        return PAYMENT
    address = settings().payment_address(method)
    if not address:
        await query.answer("Payment method not configured.", show_alert=True)
        return PAYMENT

    context.user_data["payment_method"] = method
    context.user_data["order_id"] = new_order_id()

    await query.edit_message_text(
        t(
            lang, "payment_instructions",
            method_name=strings.payment_method_name(lang, method),
            address=address,
            amount=strings.format_amount(
                lang, context.user_data["amount"], context.user_data["currency"]
            ),
            order_id=context.user_data["order_id"],
        ),
        parse_mode="Markdown",
    )
    return TRXID


async def trx_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Customer sent the transaction ID — now ask for the invite code."""
    user = update.effective_user
    lang = user_lang(user.id)
    trx_id = update.message.text.strip()
    if not TRXID_RE.match(trx_id):
        await update.message.reply_text(
            t(lang, "invalid_trxid"), parse_mode="Markdown"
        )
        return TRXID
    context.user_data["trx_id"] = trx_id
    await update.message.reply_text(
        t(lang, "ask_invite_code", trx_id=trx_id), parse_mode="Markdown"
    )
    return INVITE


async def invite_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Customer sent the invite code — save the PENDING order, notify admin."""
    user = update.effective_user
    lang = user_lang(user.id)
    invite_code = update.message.text.strip().upper()
    if not INVITE_RE.match(invite_code):
        await update.message.reply_text(
            t(lang, "invalid_invite_code"), parse_mode="Markdown"
        )
        return INVITE

    data = context.user_data
    username = f"@{user.username}" if user.username else user.full_name
    order = store().create_order(
        order_id=data["order_id"],
        user_id=user.id,
        username=username,
        region=data.get("region") or "global",
        tokens_b=data["tokens_b"],
        price_amount=data["amount"],
        currency=data["currency"],
        payment_method=data["payment_method"],
        trx_id=data["trx_id"],
        invite_code=invite_code,
    )

    await update.message.reply_text(
        t(
            lang, "order_received",
            order_id=order["order_id"],
            tokens_b=order["tokens_b"],
            amount=strings.format_amount(lang, order["price_amount"], order["currency"]),
            method_name=strings.payment_method_name(lang, order["payment_method"]),
        ),
        parse_mode="Markdown",
    )

    # Notify the admin (in the admin's language).
    alang = admin_lang()
    admin_text = t(
        alang, "admin_new_order",
        order_id=order["order_id"],
        username=username,
        user_id=user.id,
        region=region_label(order["region"]),
        tokens_b=order["tokens_b"],
        amount=strings.format_amount(alang, order["price_amount"], order["currency"]),
        method_name=strings.payment_method_name(alang, order["payment_method"]),
        trx_id=order["trx_id"],
        invite_code=order["invite_code"],
    )
    await context.bot.send_message(
        chat_id=settings().admin_telegram_id,
        text=admin_text,
        reply_markup=admin_order_keyboard(order["order_id"]),
        parse_mode="Markdown",
    )
    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    lang = user_lang(user.id)
    context.user_data.clear()
    await update.message.reply_text(t(lang, "cancelled"))
    return ConversationHandler.END


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    lang = user_lang(user.id)
    await update.message.reply_text(t(lang, "help_text"), parse_mode="Markdown")


# ---------------------------------------------------------------------------
# Admin: approve / reject
# ---------------------------------------------------------------------------
async def _is_admin(query) -> bool:
    if query.from_user.id != settings().admin_telegram_id:
        await query.answer(t("en", "not_admin"), show_alert=True)
        return False
    return True


async def approve_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await _is_admin(query):
        return
    await query.answer("Processing…")
    order_id = query.data.split(":", 1)[1]
    alang = admin_lang()
    order = store().get_order(order_id)
    if not order:
        await query.edit_message_text(f"Order `{order_id}` not found.")
        return
    if order["status"] != "PENDING":
        await query.edit_message_text(t(alang, "admin_already_processed",
                                        order_id=order_id))
        return

    # Buy from the cheapest eligible supplier (auto-fallback built in).
    try:
        async with get_router(settings()) as router:
            supplier_name, kc_order = await router.place_order(
                order["invite_code"], order["tokens_b"], order_id
            )
    except SupplierError as exc:
        # Order NOT placed (e.g. wallet empty) — stays PENDING for retry.
        await query.edit_message_text(
            t(alang, "admin_delivery_failed", order_id=order_id,
              reason=exc.message)
        )
        return

    store().update_status(
        order_id, "APPROVED",
        keycraft_order_id=kc_order.get("order_id") or "",
        supplier=supplier_name,
    )
    await query.edit_message_text(
        t(alang, "admin_approved_ok", order_id=order_id,
          keycraft_order_id=kc_order.get("order_id") or ""),
        parse_mode="Markdown",
    )

    # Tell the customer delivery has started (in the customer's language).
    clang = lang_for_region(order["region"])
    await context.bot.send_message(
        chat_id=order["user_id"],
        text=t(clang, "order_approved_delivery_started", order_id=order_id),
        parse_mode="Markdown",
    )

    # Poll delivery in the background; notify the customer when done.
    context.application.create_task(
        poll_delivery(context, order_id, kc_order.get("order_id") or "")
    )


async def reject_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await _is_admin(query):
        return
    await query.answer()
    order_id = query.data.split(":", 1)[1]
    alang = admin_lang()
    order = store().get_order(order_id)
    if not order:
        await query.edit_message_text(f"Order `{order_id}` not found.")
        return
    if order["status"] != "PENDING":
        await query.edit_message_text(t(alang, "admin_already_processed",
                                        order_id=order_id))
        return

    store().update_status(order_id, "REJECTED")
    await query.edit_message_text(
        t(alang, "admin_rejected_ok", order_id=order_id)
    )
    clang = lang_for_region(order["region"])
    await context.bot.send_message(
        chat_id=order["user_id"],
        text=t(clang, "order_rejected", order_id=order_id),
        parse_mode="Markdown",
    )


async def poll_delivery(
    context: ContextTypes.DEFAULT_TYPE, order_id: str, kc_order_id: str
) -> None:
    """Poll the supplier until the order is COMPLETED / PARTIAL / FAILED."""
    order = store().get_order(order_id)
    if not order:
        return
    supplier_name = order.get("supplier") or "keycraft"
    clang = lang_for_region(order["region"])
    alang = admin_lang()

    try:
        async with get_router(settings()) as router:
            for _ in range(settings().poll_max_attempts):
                await asyncio.sleep(settings().poll_interval_sec)
                try:
                    status = await router.get_order_status(supplier_name, kc_order_id)
                except SupplierError as exc:
                    logger.warning("Poll %s failed: %s", order_id, exc)
                    continue
                state = status.get("status", "")
                if state == "COMPLETED":
                    store().update_status(
                        order_id, "COMPLETED",
                        delivered_b=float(status.get("delivered_tokens_b") or 0),
                    )
                    await context.bot.send_message(
                        chat_id=order["user_id"],
                        text=t(
                            clang, "order_completed",
                            order_id=order_id,
                            tokens_b=order["tokens_b"],
                            invite_code=order["invite_code"],
                        ),
                        parse_mode="Markdown",
                    )
                    return
                if state == "PARTIAL":
                    delivered = float(status.get("delivered_tokens_b") or 0)
                    refunded = float(status.get("refunded_amount") or 0)
                    store().update_status(
                        order_id, "PARTIAL",
                        delivered_b=delivered, refunded_usd=refunded,
                    )
                    await context.bot.send_message(
                        chat_id=order["user_id"],
                        text=t(
                            clang, "order_partial",
                            order_id=order_id,
                            delivered_b=delivered,
                            target_b=order["tokens_b"],
                            refunded_usd=refunded,
                        ),
                        parse_mode="Markdown",
                    )
                    await context.bot.send_message(
                        chat_id=settings().admin_telegram_id,
                        text=t(
                            alang, "admin_delivery_partial",
                            order_id=order_id,
                            delivered_b=delivered,
                            target_b=order["tokens_b"],
                            refunded_usd=refunded,
                        ),
                        parse_mode="Markdown",
                    )
                    return
                if state in ("FAILED", "CANCELLED"):
                    store().update_status(order_id, "FAILED")
                    await context.bot.send_message(
                        chat_id=order["user_id"],
                        text=t(clang, "order_failed", order_id=order_id,
                               reason=f"supplier status: {state}"),
                        parse_mode="Markdown",
                    )
                    await context.bot.send_message(
                        chat_id=settings().admin_telegram_id,
                        text=t(alang, "admin_delivery_failed", order_id=order_id,
                               reason=f"supplier status: {state}"),
                    )
                    return
    except SupplierError as exc:
        logger.exception("Poll %s aborted: %s", order_id, exc)

    # Still not finished after all attempts — admin checks manually.
    await context.bot.send_message(
        chat_id=settings().admin_telegram_id,
        text=t(alang, "admin_delivery_still_running", order_id=order_id,
               keycraft_order_id=kc_order_id),
        parse_mode="Markdown",
    )


# ---------------------------------------------------------------------------
# Admin commands: /balance /status /orders /prices /setprice
# ---------------------------------------------------------------------------
def _admin_only(update: Update) -> bool:
    return update.effective_user.id == settings().admin_telegram_id


async def prices_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _admin_only(update):
        await update.message.reply_text(t("en", "not_admin"))
        return
    lang = admin_lang()
    s = settings()
    await update.message.reply_text(
        t(
            lang, "prices_info",
            price_1b=s.price_1b,
            price_5b=s.price_5b,
            price_10b=s.price_10b,
            price_30b=s.price_30b,
            price_1b_usdt=s.price_1b_usdt,
            price_5b_usdt=s.price_5b_usdt,
            price_10b_usdt=s.price_10b_usdt,
            price_30b_usdt=s.price_30b_usdt,
        ),
        parse_mode="Markdown",
    )


async def setprice_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin-only: /setprice <1B|5B|10B> <bdt_amount> [usdt_amount].

    Updates the price immediately for new orders and saves it in the
    database, so it survives bot restarts without touching env vars.
    """
    if not _admin_only(update):
        await update.message.reply_text(t("en", "not_admin"))
        return
    lang = admin_lang()
    args = context.args or []
    if len(args) not in (2, 3):
        await update.message.reply_text(
            t(lang, "setprice_usage"), parse_mode="Markdown"
        )
        return
    package = args[0].upper().rstrip("B")
    if package not in ("1", "5", "10", "30"):
        await update.message.reply_text(
            t(lang, "setprice_bad"), parse_mode="Markdown"
        )
        return
    tokens_b = int(package)
    try:
        bdt_amount = int(args[1])
        usdt_amount = int(args[2]) if len(args) == 3 else None
    except ValueError:
        await update.message.reply_text(
            t(lang, "setprice_bad"), parse_mode="Markdown"
        )
        return
    if bdt_amount <= 0 or (usdt_amount is not None and usdt_amount <= 0):
        await update.message.reply_text(
            t(lang, "setprice_bad"), parse_mode="Markdown"
        )
        return
    s = settings()
    s.set_price(tokens_b, bdt_amount, "BDT")
    store().set_setting(f"PRICE_{tokens_b}B", str(bdt_amount))
    usdt_line = ""
    if usdt_amount is not None:
        s.set_price(tokens_b, usdt_amount, "USDT")
        store().set_setting(f"PRICE_{tokens_b}B_USDT", str(usdt_amount))
        usdt_line = f", {usdt_amount} USDT"
    await update.message.reply_text(
        t(
            lang, "setprice_ok",
            tokens_b=tokens_b,
            bdt_line=f"৳{bdt_amount}" if lang == "bn" else f"{bdt_amount} BDT",
            usdt_line=usdt_line,
        ),
        parse_mode="Markdown",
    )


async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _admin_only(update):
        await update.message.reply_text(t("en", "not_admin"))
        return
    lang = admin_lang()
    parts: list[str] = []
    try:
        async with get_router(settings()) as router:
            for supplier in router.suppliers:
                balance = await supplier.get_balance()
                lifetime = balance.get("lifetime_usd")
                lifetime_line = (
                    t(lang, "lifetime_line", lifetime_usd=lifetime)
                    if lifetime is not None else ""
                )
                parts.append(
                    t(
                        lang, "balance_info",
                        supplier_name=supplier.name.title(),
                        balance_usd=balance["balance_usd"],
                        rate_per_1b=balance["rate_per_1b"],
                        lifetime_line=lifetime_line,
                        cover_b=int(
                            balance["balance_usd"] / balance["rate_per_1b"]
                        ) if balance["rate_per_1b"] else 0,
                    )
                )
    except SupplierError as exc:
        await update.message.reply_text(f"⚠️ {exc.message}")
        return
    if not parts:
        await update.message.reply_text(t(lang, "temporarily_unavailable"))
        return
    await update.message.reply_text(
        "\n\n".join(parts), parse_mode="Markdown"
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _admin_only(update):
        await update.message.reply_text(t("en", "not_admin"))
        return
    lang = admin_lang()
    parts: list[str] = []
    try:
        async with get_router(settings()) as router:
            for supplier in router.suppliers:
                stock = await supplier.check_stock()
                parts.append(
                    t(
                        lang, "status_info",
                        supplier_name=supplier.name.title(),
                        stock=stock["stock"],
                        maintenance=("YES" if stock["maintenance"] else "no")
                        if lang == "en"
                        else ("হ্যাঁ" if stock["maintenance"] else "না"),
                    )
                )
    except SupplierError as exc:
        await update.message.reply_text(f"⚠️ {exc.message}")
        return
    if not parts:
        await update.message.reply_text(t(lang, "temporarily_unavailable"))
        return
    await update.message.reply_text(
        "\n\n".join(parts), parse_mode="Markdown"
    )


async def orders_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _admin_only(update):
        await update.message.reply_text(t("en", "not_admin"))
        return
    lang = admin_lang()
    pending = store().list_orders(status="PENDING", limit=10)
    if not pending:
        await update.message.reply_text(t(lang, "no_pending_orders"))
        return
    lines = [t(lang, "pending_orders_header")]
    keyboard_rows = []
    for order in pending:
        lines.append(
            t(
                lang, "pending_order_line",
                order_id=order["order_id"],
                tokens_b=order["tokens_b"],
                amount=strings.format_amount(
                    lang, order["price_amount"], order["currency"]
                ),
                method_name=strings.payment_method_name(
                    lang, order["payment_method"]
                ),
                trx_id=order["trx_id"],
                invite_code=order["invite_code"],
            )
        )
        keyboard_rows.append(
            [
                InlineKeyboardButton(
                    f"✅ {order['order_id']}",
                    callback_data=f"approve:{order['order_id']}",
                ),
                InlineKeyboardButton(
                    f"❌ {order['order_id']}",
                    callback_data=f"reject:{order['order_id']}",
                ),
            ]
        )
    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard_rows),
        parse_mode="Markdown",
    )


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
def build_application(settings_obj: Settings) -> Application:
    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("language", start),
        ],
        states={
            REGION: [
                CallbackQueryHandler(region_chosen, pattern=r"^region:(bd|global)$"),
            ],
            PACKAGE: [
                CallbackQueryHandler(package_chosen, pattern=r"^pkg:\d+$"),
                CallbackQueryHandler(change_region, pattern=r"^change_region$"),
            ],
            PAYMENT: [
                CallbackQueryHandler(payment_chosen, pattern=r"^pay:\w+$"),
                CallbackQueryHandler(back_to_packages, pattern=r"^back:packages$"),
            ],
            TRXID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, trx_received),
            ],
            INVITE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, invite_received),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        conversation_timeout=900,  # 15 min of silence ends the order flow
    )

    app = Application.builder().token(settings_obj.telegram_bot_token).build()
    app.add_handler(conv)
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("orders", orders_command))
    app.add_handler(CommandHandler("prices", prices_command))
    app.add_handler(CommandHandler("setprice", setprice_command))
    app.add_handler(CallbackQueryHandler(approve_order, pattern=r"^approve:.+"))
    app.add_handler(CallbackQueryHandler(reject_order, pattern=r"^reject:.+"))
    return app


def main() -> None:
    global SETTINGS, STORE
    load_dotenv()
    SETTINGS = Settings()
    missing = SETTINGS.validate()
    if missing:
        print(f"ERROR: missing required env vars: {', '.join(missing)}")
        print("Copy .env.example to .env and fill in the real values.")
        sys.exit(1)
    for name in SETTINGS.payment_warnings():
        logger.warning("Payment detail %s is not set — that method is hidden.", name)
    if not get_suppliers(SETTINGS):
        print("ERROR: no supplier configured (KEYCRAFT_API_KEY is missing).")
        sys.exit(1)
    STORE = OrderStore(SETTINGS.db_path)
    # Admin-set price overrides (/setprice) win over env vars, so a price
    # changed from Telegram survives restarts without touching FadeHost.
    SETTINGS.apply_overrides(STORE.get_all_settings())
    logger.info("Starting %s …", strings.BOT_DISPLAY_NAME)
    build_application(SETTINGS).run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
