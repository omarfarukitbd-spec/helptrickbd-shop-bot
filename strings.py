"""All user-facing bot messages live in this file — in Bangla AND English.

Region decides the language:
  * "bd"     -> Bangla ("bn"), payments: bKash / Nagad / Binance Pay
  * "global" -> English ("en"), payment: Binance Pay only

To change wording, edit only this file. Nothing else in the project
contains customer-facing text.

Usage:  t(lang, "welcome")  or  t(lang, "order_received", order_id="...")
"""

BOT_DISPLAY_NAME = "Muse Token Store"

# Region buttons shown right after /start (same labels in both languages).
REGION_BUTTONS = {
    "bd": "🇧🇩 বাংলাদেশ",
    "global": "🌍 Global",
}


def lang_for_region(region: str | None) -> str:
    """'bd' -> 'bn', anything else -> 'en'."""
    return "bn" if region == "bd" else "en"


def payment_method_name(lang: str, method: str) -> str:
    names = {
        "en": {"bkash": "bKash", "nagad": "Nagad", "binance": "Binance Pay"},
        "bn": {"bkash": "বিকাশ", "nagad": "নগদ", "binance": "Binance Pay"},
    }
    return names.get(lang, names["en"]).get(method, method)


def format_amount(lang: str, amount: int, currency: str) -> str:
    """'100 BDT' / '৳100' for BDT, '1 USDT' for USDT."""
    if currency == "BDT":
        return f"৳{amount}" if lang == "bn" else f"{amount} BDT"
    return f"{amount} {currency}"


def package_button(lang: str, tokens_b: int, amount: int, currency: str) -> str:
    if lang == "bn":
        return f"🪙 {tokens_b}B টোকেন — {format_amount(lang, amount, currency)}"
    return f"🪙 {tokens_b}B Tokens — {format_amount(lang, amount, currency)}"


STRINGS = {
    # ------------------------------------------------------------------
    "en": {
        "choose_region": (
            "Please choose your region:\n"
            "আপনার অঞ্চল বেছে নিন:"
        ),
        "region_saved_bd": (
            "✅ Bangladesh selected. The bot will now speak Bangla.\n"
            "You can change this anytime with /language."
        ),
        "region_saved_global": (
            "✅ Global region selected. The bot will now speak English.\n"
            "You can change this anytime with /language."
        ),
        "welcome": (
            "👋 Welcome to Muse Token Store!\n\n"
            "Buy Muse AI tokens instantly and securely.\n"
            "Choose a package below to get started:"
        ),
        "choose_payment": (
            "You selected *{tokens_b}B Tokens* — *{amount}*.\n\n"
            "How would you like to pay?"
        ),
        "payment_instructions": (
            "💳 *Payment — {method_name}*\n\n"
            "Please send exactly *{amount}* to:\n"
            "`{address}`\n\n"
            "🧾 Your order ID: `{order_id}`\n\n"
            "After you send the payment, reply here with your "
            "*transaction ID* (TrxID / TxID)."
        ),
        "ask_invite_code": (
            "✅ Transaction ID received: `{trx_id}`\n\n"
            "Now send your *Muse invite code* "
            "(the code you use to create / top up your Muse account).\n"
            "Example: `TCJLWV`"
        ),
        "order_received": (
            "🎉 *Order received!*\n\n"
            "🧾 Order ID: `{order_id}`\n"
            "🪙 Package: {tokens_b}B Tokens\n"
            "💰 Paid: {amount} via {method_name}\n\n"
            "Your payment is being verified by our team. "
            "You will get your tokens as soon as it is approved — "
            "usually within a few minutes."
        ),
        "order_approved_delivery_started": (
            "✅ *Payment confirmed!*\n\n"
            "🧾 Order ID: `{order_id}`\n"
            "Your tokens are being delivered now. Please wait a moment…"
        ),
        "order_completed": (
            "🎉 *Tokens delivered!*\n\n"
            "🧾 Order ID: `{order_id}`\n"
            "🪙 {tokens_b}B Muse tokens have been delivered to "
            "invite code `{invite_code}`.\n\n"
            "Thank you for shopping with us! "
            "Send /start if you would like to buy again."
        ),
        "order_partial": (
            "⚠️ *Order partially delivered*\n\n"
            "🧾 Order ID: `{order_id}`\n"
            "🪙 Delivered: {delivered_b}B out of {target_b}B tokens.\n"
            "💵 Refunded to our wallet: ${refunded_usd:.2f} "
            "(the undelivered part).\n\n"
            "Please contact support and share your order ID — "
            "we will arrange the remaining tokens or a refund."
        ),
        "order_rejected": (
            "❌ *Order rejected*\n\n"
            "🧾 Order ID: `{order_id}`\n"
            "We could not verify your payment. "
            "Please double-check your transaction ID and try again, "
            "or contact support for help."
        ),
        "order_failed": (
            "⚠️ *Delivery problem*\n\n"
            "🧾 Order ID: `{order_id}`\n"
            "Reason: {reason}\n\n"
            "Our team has been notified and will fix this for you. "
            "Please keep your order ID safe."
        ),
        "out_of_stock": (
            "😔 Sorry, tokens are temporarily out of stock.\n"
            "Please try again in a little while."
        ),
        "maintenance": (
            "🛠️ Token delivery is under maintenance right now.\n"
            "Please try again later."
        ),
        "temporarily_unavailable": (
            "😔 Sorry, this package is temporarily unavailable.\n"
            "Please try a smaller package or try again later."
        ),
        "invalid_trxid": (
            "❌ That doesn't look like a valid transaction ID.\n"
            "Please send only your TrxID / TxID "
            "(for example: `9X7A12BC84`)."
        ),
        "invalid_invite_code": (
            "❌ That doesn't look like a valid invite code.\n"
            "Please send only your Muse invite code "
            "(for example: `TCJLWV`)."
        ),
        "cancelled": (
            "Order cancelled. Send /start whenever you're ready to buy."
        ),
        "error_generic": (
            "⚠️ Something went wrong on our side. "
            "Please try again in a moment."
        ),
        "not_admin": "⛔ This command is for the admin only.",
        "help_text": (
            "🤖 *Muse Token Store*\n\n"
            "Buy Muse AI tokens in 3 easy steps:\n"
            "1️⃣ Send /start and choose a package (1B / 5B / 10B).\n"
            "2️⃣ Pay with bKash, Nagad or Binance Pay.\n"
            "3️⃣ Send your TrxID and your Muse invite code.\n\n"
            "Your tokens are delivered after payment verification.\n"
            "Use /language to change your region / language.\n"
            "Use /cancel anytime to stop an order."
        ),
        "language_button": "🌐 Language / ভাষা পরিবর্তন",
        "back_button": "⬅️ Back",
        # -- admin --
        "admin_new_order": (
            "🆕 *New pending order*\n\n"
            "🧾 Order ID: `{order_id}`\n"
            "👤 Customer: {username} (`{user_id}`)\n"
            "🌍 Region: {region}\n"
            "🪙 Package: {tokens_b}B Tokens\n"
            "💰 Amount: {amount} via {method_name}\n"
            "🔑 TrxID: `{trx_id}`\n"
            "🎟️ Invite code: `{invite_code}`\n\n"
            "Please verify the payment, then Approve or Reject."
        ),
        "admin_approved_ok": (
            "✅ Order `{order_id}` approved.\n"
            "KeyCraft order: `{keycraft_order_id}`\n"
            "Delivering — the customer will be notified automatically."
        ),
        "admin_rejected_ok": (
            "❌ Order `{order_id}` rejected. The customer has been notified."
        ),
        "admin_already_processed": (
            "ℹ️ Order `{order_id}` was already processed."
        ),
        "admin_delivery_failed": (
            "⚠️ Delivery failed for order `{order_id}`.\n"
            "Reason: {reason}\n"
            "Please check the KeyCraft dashboard / balance and handle manually."
        ),
        "admin_delivery_partial": (
            "⚠️ Order `{order_id}` partially delivered: "
            "{delivered_b}B of {target_b}B. Refunded: ${refunded_usd:.2f}."
        ),
        "admin_delivery_still_running": (
            "⏳ Order `{order_id}` is still delivering "
            "(KeyCraft order `{keycraft_order_id}`).\n"
            "Automatic checks stopped — please verify it manually with /orders "
            "or on the KeyCraft dashboard."
        ),
        "balance_info": (
            "💰 *{supplier_name} wallet*\n\n"
            "Balance: *${balance_usd:.2f}*\n"
            "Rate: *${rate_per_1b:.2f} per 1B tokens*\n"
            "{lifetime_line}"
            "\nThat balance covers about *{cover_b}B* tokens."
        ),
        "lifetime_line": "Lifetime usage: ${lifetime_usd:.2f}\n",
        "status_info": (
            "📦 *{supplier_name} stock status*\n\n"
            "Stock: *{stock}*\n"
            "Maintenance: *{maintenance}*"
        ),
        "pending_orders_header": "📋 *Pending orders:*\n",
        "pending_order_line": (
            "• `{order_id}` — {tokens_b}B, {amount}, {method_name}, "
            "TrxID `{trx_id}`, code `{invite_code}`"
        ),
        "no_pending_orders": "📋 No pending orders. All clear! ✅",
        "prices_info": (
            "💲 *Current prices*\n\n"
            "🇧🇩 Bangladesh (BDT):\n"
            "• 1B — {price_1b} BDT\n"
            "• 5B — {price_5b} BDT\n"
            "• 10B — {price_10b} BDT\n\n"
            "🌍 Global (USDT):\n"
            "• 1B — {price_1b_usdt} USDT\n"
            "• 5B — {price_5b_usdt} USDT\n"
            "• 10B — {price_10b_usdt} USDT\n\n"
            "Change a price with:\n"
            "`/setprice 1B 120` — sets the 1B BDT price to ৳120\n"
            "`/setprice 5B 200 4` — sets 5B to ৳200 and $4 USDT"
        ),
        "setprice_usage": (
            "Usage:\n"
            "`/setprice 1B 120` — set the 1B Bangladesh price to ৳120\n"
            "`/setprice 5B 200 4` — set 5B to ৳200 and $4 USDT\n"
            "Package must be 1B, 5B or 10B. See current prices with /prices."
        ),
        "setprice_ok": (
            "✅ Price updated:\n"
            "• {tokens_b}B — {bdt_line}{usdt_line}\n\n"
            "New prices take effect immediately for new orders."
        ),
        "setprice_bad": (
            "⚠️ That did not work. Check the format:\n"
            "`/setprice 1B 120` or `/setprice 5B 200 4`\n"
            "Amounts must be positive numbers."
        ),
    },
    # ------------------------------------------------------------------
    "bn": {
        "choose_region": (
            "Please choose your region:\n"
            "আপনার অঞ্চল বেছে নিন:"
        ),
        "region_saved_bd": (
            "✅ বাংলাদেশ নির্বাচন করা হয়েছে। এখন থেকে বটটি বাংলায় চলবে।\n"
            "যেকোনো সময় /language লিখে বদলাতে পারবেন।"
        ),
        "region_saved_global": (
            "✅ Global অঞ্চল নির্বাচন করা হয়েছে। এখন থেকে বটটি English-এ চলবে।\n"
            "যেকোনো সময় /language লিখে বদলাতে পারবেন।"
        ),
        "welcome": (
            "👋 Muse Token Store-এ স্বাগতম!\n\n"
            "Muse AI টোকেন কিনুন সহজে ও নিরাপদে।\n"
            "নিচে থেকে একটি প্যাকেজ বেছে নিন:"
        ),
        "choose_payment": (
            "আপনি বেছে নিয়েছেন *{tokens_b}B টোকেন* — *{amount}*।\n\n"
            "কীভাবে পেমেন্ট করতে চান?"
        ),
        "payment_instructions": (
            "💳 *পেমেন্ট — {method_name}*\n\n"
            "অনুগ্রহ করে ঠিক *{amount}* পাঠান:\n"
            "`{address}`\n\n"
            "🧾 আপনার অর্ডার আইডি: `{order_id}`\n\n"
            "পেমেন্ট পাঠানোর পর এখানে আপনার "
            "*ট্রানজাকশন আইডি* (TrxID / TxID) লিখে পাঠান।"
        ),
        "ask_invite_code": (
            "✅ ট্রানজাকশন আইডি পেয়েছি: `{trx_id}`\n\n"
            "এখন আপনার *Muse ইনভাইট কোড* পাঠান "
            "(যে কোড দিয়ে আপনি Muse অ্যাকাউন্ট তৈরি / টপ আপ করেন)।\n"
            "উদাহরণ: `TCJLWV`"
        ),
        "order_received": (
            "🎉 *অর্ডার পেয়েছি!*\n\n"
            "🧾 অর্ডার আইডি: `{order_id}`\n"
            "🪙 প্যাকেজ: {tokens_b}B টোকেন\n"
            "💰 পেমেন্ট: {amount} ({method_name})\n\n"
            "আপনার পেমেন্ট যাচাই করা হচ্ছে। অনুমোদন হলেই টোকেন পেয়ে যাবেন — "
            "সাধারণত কয়েক মিনিটের মধ্যে।"
        ),
        "order_approved_delivery_started": (
            "✅ *পেমেন্ট নিশ্চিত হয়েছে!*\n\n"
            "🧾 অর্ডার আইডি: `{order_id}`\n"
            "আপনার টোকেন পাঠানো হচ্ছে। একটু অপেক্ষা করুন…"
        ),
        "order_completed": (
            "🎉 *টোকেন পৌঁছে গেছে!*\n\n"
            "🧾 অর্ডার আইডি: `{order_id}`\n"
            "🪙 {tokens_b}B Muse টোকেন আপনার ইনভাইট কোড "
            "`{invite_code}`-এ পাঠানো হয়েছে।\n\n"
            "আমাদের থেকে কেনার জন্য ধন্যবাদ! "
            "আবার কিনতে চাইলে /start লিখুন।"
        ),
        "order_partial": (
            "⚠️ *আংশিক ডেলিভারি হয়েছে*\n\n"
            "🧾 অর্ডার আইডি: `{order_id}`\n"
            "🪙 পৌঁছেছে: {delivered_b}B (মোট {target_b}B-এর মধ্যে)।\n"
            "💵 ফেরত: ${refunded_usd:.2f} "
            "(বাকি অংশের টাকা আমাদের ওয়ালেটে ফেরত এসেছে)।\n\n"
            "অনুগ্রহ করে আপনার অর্ডার আইডিসহ সাপোর্টে যোগাযোগ করুন — "
            "বাকি টোকেন বা রিফান্ডের ব্যবস্থা করা হবে।"
        ),
        "order_rejected": (
            "❌ *অর্ডার বাতিল হয়েছে*\n\n"
            "🧾 অর্ডার আইডি: `{order_id}`\n"
            "আপনার পেমেন্ট যাচাই করা যায়নি। "
            "ট্রানজাকশন আইডি ঠিক আছে কি না দেখে আবার চেষ্টা করুন, "
            "অথবা সাপোর্টে যোগাযোগ করুন।"
        ),
        "order_failed": (
            "⚠️ *ডেলিভারিতে সমস্যা হয়েছে*\n\n"
            "🧾 অর্ডার আইডি: `{order_id}`\n"
            "কারণ: {reason}\n\n"
            "আমাদের টিমকে জানানো হয়েছে, তারা ঠিক করে দেবে। "
            "আপনার অর্ডার আইডি সংরক্ষণ করুন।"
        ),
        "out_of_stock": (
            "😔 দুঃখিত, আপাতত টোকেন শেষ।\n"
            "কিছুক্ষণ পর আবার চেষ্টা করুন।"
        ),
        "maintenance": (
            "🛠️ টোকেন ডেলিভারি এখন রক্ষণাবেক্ষণে আছে।\n"
            "পরে আবার চেষ্টা করুন।"
        ),
        "temporarily_unavailable": (
            "😔 দুঃখিত, এই প্যাকেজটি আপাতত পাওয়া যাচ্ছে না।\n"
            "ছোট প্যাকেজ চেষ্টা করুন বা পরে আবার চেষ্টা করুন।"
        ),
        "invalid_trxid": (
            "❌ এটা সঠিক ট্রানজাকশন আইডি মনে হচ্ছে না।\n"
            "শুধু আপনার TrxID / TxID পাঠান (যেমন: `9X7A12BC84`)।"
        ),
        "invalid_invite_code": (
            "❌ এটা সঠিক ইনভাইট কোড মনে হচ্ছে না।\n"
            "শুধু আপনার Muse ইনভাইট কোড পাঠান (যেমন: `TCJLWV`)।"
        ),
        "cancelled": (
            "অর্ডার বাতিল হয়েছে। কিনতে চাইলে যেকোনো সময় /start লিখুন।"
        ),
        "error_generic": (
            "⚠️ আমাদের দিকে কিছু একটা সমস্যা হয়েছে। "
            "একটু পর আবার চেষ্টা করুন।"
        ),
        "not_admin": "⛔ এই কমান্ডটি শুধু অ্যাডমিনের জন্য।",
        "help_text": (
            "🤖 *Muse Token Store*\n\n"
            "মাত্র ৩ ধাপে Muse AI টোকেন কিনুন:\n"
            "1️⃣ /start লিখে প্যাকেজ বেছে নিন (1B / 5B / 10B)।\n"
            "2️⃣ বিকাশ, নগদ বা Binance Pay দিয়ে পেমেন্ট করুন।\n"
            "3️⃣ TrxID ও আপনার Muse ইনভাইট কোড পাঠান।\n\n"
            "পেমেন্ট যাচাই হলেই টোকেন পৌঁছে যাবে।\n"
            "অঞ্চল / ভাষা বদলাতে /language লিখুন।\n"
            "অর্ডার বাতিল করতে /cancel লিখুন।"
        ),
        "language_button": "🌐 Language / ভাষা পরিবর্তন",
        "back_button": "⬅️ ফিরে যান",
        # -- admin --
        "admin_new_order": (
            "🆕 *নতুন অর্ডার (pending)*\n\n"
            "🧾 অর্ডার আইডি: `{order_id}`\n"
            "👤 কাস্টমার: {username} (`{user_id}`)\n"
            "🌍 অঞ্চল: {region}\n"
            "🪙 প্যাকেজ: {tokens_b}B টোকেন\n"
            "💰 পরিমাণ: {amount} ({method_name})\n"
            "🔑 TrxID: `{trx_id}`\n"
            "🎟️ ইনভাইট কোড: `{invite_code}`\n\n"
            "পেমেন্ট যাচাই করে Approve বা Reject করুন।"
        ),
        "admin_approved_ok": (
            "✅ অর্ডার `{order_id}` অনুমোদন করা হয়েছে।\n"
            "KeyCraft অর্ডার: `{keycraft_order_id}`\n"
            "ডেলিভারি চলছে — কাস্টমারকে স্বয়ংক্রিয়ভাবে জানানো হবে।"
        ),
        "admin_rejected_ok": (
            "❌ অর্ডার `{order_id}` বাতিল করা হয়েছে। কাস্টমারকে জানানো হয়েছে।"
        ),
        "admin_already_processed": (
            "ℹ️ অর্ডার `{order_id}` আগেই প্রসেস করা হয়েছে।"
        ),
        "admin_delivery_failed": (
            "⚠️ অর্ডার `{order_id}`-এর ডেলিভারি ব্যর্থ হয়েছে।\n"
            "কারণ: {reason}\n"
            "KeyCraft ড্যাশবোর্ড / ব্যালান্স চেক করে নিজে ব্যবস্থা নিন।"
        ),
        "admin_delivery_partial": (
            "⚠️ অর্ডার `{order_id}` আংশিক ডেলিভারি হয়েছে: "
            "{target_b}B-এর মধ্যে {delivered_b}B। ফেরত: ${refunded_usd:.2f}।"
        ),
        "admin_delivery_still_running": (
            "⏳ অর্ডার `{order_id}` এখনো ডেলিভারি হচ্ছে "
            "(KeyCraft অর্ডার `{keycraft_order_id}`)।\n"
            "স্বয়ংক্রিয় চেক বন্ধ হয়েছে — /orders বা KeyCraft ড্যাশবোর্ড "
            "থেকে নিজে যাচাই করুন।"
        ),
        "balance_info": (
            "💰 *{supplier_name} ওয়ালেট*\n\n"
            "ব্যালান্স: *${balance_usd:.2f}*\n"
            "রেট: *প্রতি 1B টোকেনে ${rate_per_1b:.2f}*\n"
            "{lifetime_line}"
            "\nএই ব্যালান্সে প্রায় *{cover_b}B* টোকেন কেনা যাবে।"
        ),
        "lifetime_line": "মোট ব্যবহার: ${lifetime_usd:.2f}\n",
        "status_info": (
            "📦 *{supplier_name} স্টক*\n\n"
            "স্টক: *{stock}*\n"
            "রক্ষণাবেক্ষণ: *{maintenance}*"
        ),
        "pending_orders_header": "📋 *অপেক্ষমাণ অর্ডার:*\n",
        "pending_order_line": (
            "• `{order_id}` — {tokens_b}B, {amount}, {method_name}, "
            "TrxID `{trx_id}`, কোড `{invite_code}`"
        ),
        "no_pending_orders": "📋 কোনো অপেক্ষমাণ অর্ডার নেই। সব ঠিক আছে! ✅",
        "prices_info": (
            "💲 *বর্তমান দাম*\n\n"
            "🇧🇩 বাংলাদেশ (টাকা):\n"
            "• 1B — ৳{price_1b}\n"
            "• 5B — ৳{price_5b}\n"
            "• 10B — ৳{price_10b}\n\n"
            "🌍 Global (USDT):\n"
            "• 1B — {price_1b_usdt} USDT\n"
            "• 5B — {price_5b_usdt} USDT\n"
            "• 10B — {price_10b_usdt} USDT\n\n"
            "দাম বদলাতে লিখুন:\n"
            "`/setprice 1B 120` — 1B-এর দাম ৳১২০ হবে\n"
            "`/setprice 5B 200 4` — 5B হবে ৳৪৫০ আর $4 USDT"
        ),
        "setprice_usage": (
            "ব্যবহার:\n"
            "`/setprice 1B 120` — 1B-এর বাংলাদেশি দাম ৳১২০ হবে\n"
            "`/setprice 5B 200 4` — 5B হবে ৳৪৫০ আর $4 USDT\n"
            "প্যাকেজ 1B, 5B বা 10B হতে হবে। বর্তমান দাম দেখতে /prices লিখুন।"
        ),
        "setprice_ok": (
            "✅ দাম বদলে গেছে:\n"
            "• {tokens_b}B — {bdt_line}{usdt_line}\n\n"
            "নতুন দাম এখনই নতুন অর্ডারে কাজ করবে।"
        ),
        "setprice_bad": (
            "⚠️ হয়নি। ঠিকভাবে লিখুন:\n"
            "`/setprice 1B 120` বা `/setprice 5B 200 4`\n"
            "দাম অবশ্যই ধনাত্মক সংখ্যা হতে হবে।"
        ),
    },
}


def t(lang: str, key: str, **kwargs) -> str:
    """Render a user-facing string in `lang` ('bn' or 'en')."""
    table = STRINGS.get(lang) or STRINGS["en"]
    template = table.get(key) or STRINGS["en"].get(key, key)
    return template.format(**kwargs)
