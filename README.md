# Muse Token Store — KeyCraft Telegram Reseller Bot

A Telegram bot that sells Muse AI tokens. Customers pick a package,
pay with bKash / Nagad / Binance Pay, send their transaction ID and Muse
invite code — the admin approves with one tap and the bot delivers the
tokens through the KeyCraft Reseller API.

## What it does

- **Region first:** `/start` shows two options — **🇧🇩 বাংলাদেশ**
  (entire UI in Bangla; payments: bKash + Nagad + Binance Pay) and
  **🌍 Global** (entire UI in English; payment: Binance Pay only).
  Each user's choice is saved; `/language` (or the 🌐 button) switches it.
- **Packages:** 1B / 5B / 10B / 30B tokens. Prices are env vars —
  BDT defaults 30 / 150 / 300 / 900, USDT defaults 1 / 4 / 7 / 21.
- **Semi-auto payment:** customer pays, sends TrxID + invite code,
  order is saved as PENDING, admin gets it with **Approve / Reject**
  buttons. On Approve the bot buys the tokens and polls delivery until
  COMPLETED (or PARTIAL, with the auto-refund noted), then notifies
  the customer.
- **Cheapest-supplier routing:** before every order the bot compares
  the **live rate per 1B** across all configured suppliers, keeps only
  suppliers that are IN_STOCK with enough wallet balance, and buys from
  the **cheapest**. If the cheapest fails, it falls back to the next
  cheapest automatically. Each supplier spends from its **own** wallet —
  money is never moved between suppliers.
- **Admin commands:** `/balance` (wallet + live rate per supplier),
  `/status` (stock per supplier), `/orders` (pending orders with
  Approve / Reject buttons), `/prices` (current package prices),
  `/setprice` (change a price from Telegram, e.g. `/setprice 1B 120`
  or `/setprice 5B 150 4` for BDT + USDT — takes effect immediately
  for new orders and survives restarts, no FadeHost visit needed).
- **Safety checks:** before accepting an order the bot checks live stock
  and balance, and refuses politely on OUT_OF_STOCK, MAINTENANCE, or
  low balance.
- **All user-facing text lives in `strings.py`** (Bangla + English) —
  change wording or add a language by editing one file.

## Project structure

```
keycraft-bot/
├── bot.py               # Telegram bot: conversations, admin panel, polling
├── config.py            # Settings from env vars (prices, payment numbers)
├── strings.py           # ALL user-facing text: Bangla ("bn") + English ("en")
├── storage.py           # SQLite orders + saved user regions
├── suppliers/
│   ├── __init__.py      # Factory: which suppliers are configured
│   ├── base.py          # Supplier interface (check_stock, get_balance,
│   │                    #   place_order, get_order_status)
│   ├── keycraft.py      # KeyCraft implementation (the only supplier today)
│   └── router.py        # Cheapest-first routing + fallback
├── tests/
│   └── test_suppliers.py  # Offline tests (mock API, no real calls)
├── requirements.txt
├── Procfile             # worker: python bot.py  (FadeHost)
├── runtime.txt          # python-3.12
├── .env.example         # Copy to .env and fill in your own values
└── README.md
```

## Setup — step by step

### 1. Create the Telegram bot (2 minutes)

1. Open **@BotFather** in Telegram, send `/newbot`.
2. Choose a display name (e.g. `Muse Token Store`) and a username
   ending in `bot` (e.g. `MuseTokenStoreBot`).
3. Copy the **bot token** BotFather gives you → `TELEGRAM_BOT_TOKEN`.

### 2. Get your KeyCraft API key + top up $2 for testing

1. Open **@KeyCraftShopBot** in Telegram (or https://enterpriceai.store)
   and create your reseller API key. This must be **your own** key —
   every order charges the wallet that owns the key.
2. Top up the wallet with **$2** for the first test.
   At $0.06 per 1B tokens, $2 buys ≈ **33B tokens** — enough for many
   test orders. Top up more only after the test works.
3. Copy the key → `KEYCRAFT_API_KEY`. Never paste it in a chat or
   commit it to GitHub.

### 3. Get your Telegram user ID

Send any message to **@userinfobot** — it replies with your numeric ID
→ `ADMIN_TELEGRAM_ID`. Only this ID can approve orders and use
`/balance`, `/status`, `/orders`.

### 4. Configure

```bash
git clone <your-repo-url> keycraft-bot
cd keycraft-bot
cp .env.example .env
# edit .env with your real values (see the table below)
```

| Variable | What it is |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather |
| `KEYCRAFT_API_KEY` | Your own KeyCraft reseller key |
| `KEYCRAFT_BASE_URL` | `https://enterpriceai.store/api/v1` (default) |
| `ADMIN_TELEGRAM_ID` | Your numeric Telegram user ID |
| `BKASH_NUMBER` | Your bKash Send Money number (e.g. `01XXXXXXXXX`) |
| `NAGAD_NUMBER` | Your Nagad Send Money number |
| `BINANCE_PAY_ID` | Your Binance Pay ID (USDT) |
| `PRICE_1B` / `PRICE_5B` / `PRICE_10B` / `PRICE_30B` | Bangladesh prices in BDT (default 30 / 150 / 300 / 900) |
| `PRICE_1B_USDT` / `PRICE_5B_USDT` / `PRICE_10B_USDT` | Global prices in USDT (default 1 / 4 / 7) |
| `DB_PATH` | SQLite file (default `orders.db`) |
| `POLL_INTERVAL_SEC` / `POLL_MAX_ATTEMPTS` | Delivery polling (default 15s × 120 = 30 min) |

### 5. Run locally (test)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests -v   # offline tests, no real API calls
python bot.py
```

### 6. Test with a real 1B order ($0.06)

1. Make sure the wallet has the $2 top-up (check with `/balance`
   from your admin account once the bot runs).
2. From a **second** Telegram account (or ask a friend), open the bot:
   `/start` → pick a region → pick **1B** → pay the exact amount →
   send your TrxID → send a real Muse invite code.
3. From your admin account, tap **✅ Approve** on the pending order.
4. The bot calls the KeyCraft API and polls until COMPLETED, then
   messages the customer "🎉 Tokens delivered!".
5. Cost of this test: **$0.06** (1B × $0.06). If anything fails, the
   order stays PENDING and the admin is told why — nothing is charged
   twice (orders are idempotent via the order ID).

## Deploy on FadeHost (free tier)

FadeHost's free bot plan: 1 bot, 256 MB RAM, no credit card, no sleep,
no renewal — enough for this bot.

1. Push this folder to a **private** GitHub repo (never commit `.env`
   or `*.db` — `.gitignore` already excludes them).
2. Sign up at https://fadehost.com (email only, no card).
3. Create a new **Telegram bot / app**, connect your GitHub repo.
4. Set the start command to `python bot.py`
   (or use the included `Procfile`: `worker: python bot.py`).
5. Add **all** variables from `.env.example` in the FadeHost panel's
   environment variables section — with your real values.
6. Deploy. Open your bot in Telegram and send `/start`.

If the bot ever outgrows the free tier, the code is plain Python with
no FadeHost-specific parts — move the same repo to any VPS and run
`python bot.py` there (use `systemd` to keep it running).

## Adding a second supplier later

1. Write a `Supplier` subclass in `suppliers/` (see `suppliers/base.py`
   — four methods: `check_stock`, `get_balance`, `place_order`,
   `get_order_status`). Give it a distinct `name`.
2. Register it in `suppliers/__init__.py:get_suppliers()`, guarded by
   its own API-key env var.
3. Done — the router compares live rates and picks the cheapest
   automatically. No change to `bot.py` is needed.
4. Note: each supplier needs **your own** account + API key on that
   platform, and each key charges its own separate wallet.

## Troubleshooting

| Problem | What to check |
|---|---|
| Bot says "missing required env vars" | `.env` is missing or `TELEGRAM_BOT_TOKEN` / `KEYCRAFT_API_KEY` / `ADMIN_TELEGRAM_ID` is empty. |
| `402 INSUFFICIENT_BALANCE` on approve | Top up the supplier wallet (see `/balance`). The order stays PENDING — approve again after top-up. |
| `409 OUT_OF_STOCK` / `503 MAINTENANCE` | Supplier pool empty or in maintenance — wait and retry; check `/status`. |
| `429 RATE_LIMITED` | KeyCraft default limit is 120 requests/min — wait a minute. |
| Customer never gets tokens | Check `/orders` and the bot logs; a PARTIAL delivery refunds the undelivered part to the wallet automatically. |
| A payment method is missing from the menu | Its number/ID is not set in env vars (see startup warnings). |
| Orders from a region show the wrong language | The user's region is saved at `/start`; they can change it with `/language`. |

## Security notes

- Secrets live **only** in env vars / the host panel — never in code,
  never in Git, never pasted in a chat.
- The bot token and API key are only ever sent to Telegram's and
  KeyCraft's servers respectively.
- Orders are idempotent: the same order ID can never be charged twice
  by the same supplier.
- Keep the repo **private** — `orders.db` contains customer TrxIDs
  and invite codes.
