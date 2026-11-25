"""Configuration for the KeyCraft token-reseller bot.

Every secret and every tunable value comes from environment variables.
Nothing sensitive is hardcoded anywhere in this project.
"""

import os


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


class Settings:
    """All settings, read from the environment at startup."""

    def __init__(self) -> None:
        # --- Secrets (never commit real values) ---
        self.telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.keycraft_api_key: str = os.getenv("KEYCRAFT_API_KEY", "")
        self.admin_telegram_id: int = _int_env("ADMIN_TELEGRAM_ID", 0)

        # --- KeyCraft API ---
        self.keycraft_base_url: str = os.getenv(
            "KEYCRAFT_BASE_URL", "https://enterpriceai.store/api/v1"
        ).rstrip("/")
        # Cost of 1B tokens in USD (KeyCraft rate). Used as a fallback if the
        # live /reseller/balance response does not include the rate.
        self.token_cost_per_b: float = 0.06

        # --- Payment details shown to customers ---
        self.bkash_number: str = os.getenv("BKASH_NUMBER", "")
        self.nagad_number: str = os.getenv("NAGAD_NUMBER", "")
        self.binance_pay_id: str = os.getenv("BINANCE_PAY_ID", "")

        # --- Package prices ---
        # Bangladesh pays in BDT (bKash / Nagad / Binance Pay).
        self.price_1b: int = _int_env("PRICE_1B", 40)
        self.price_5b: int = _int_env("PRICE_5B", 200)
        self.price_10b: int = _int_env("PRICE_10B", 400)
        # Global users pay in USDT (Binance Pay only). Defaults are the
        # USDT equivalents of the BDT prices above.
        self.price_1b_usdt: int = _int_env("PRICE_1B_USDT", 1)
        self.price_5b_usdt: int = _int_env("PRICE_5B_USDT", 4)
        self.price_10b_usdt: int = _int_env("PRICE_10B_USDT", 7)

        # --- Storage / delivery polling ---
        self.db_path: str = os.getenv("DB_PATH", "orders.db")
        self.poll_interval_sec: int = _int_env("POLL_INTERVAL_SEC", 15)
        self.poll_max_attempts: int = _int_env("POLL_MAX_ATTEMPTS", 120)

    # -- prices ------------------------------------------------------------
    # Env var names for the six prices, keyed by (tokens_b, currency).
    PRICE_KEYS: dict[tuple[int, str], str] = {
        (1, "BDT"): "PRICE_1B",
        (5, "BDT"): "PRICE_5B",
        (10, "BDT"): "PRICE_10B",
        (1, "USDT"): "PRICE_1B_USDT",
        (5, "USDT"): "PRICE_5B_USDT",
        (10, "USDT"): "PRICE_10B_USDT",
    }

    def set_price(self, tokens_b: int, amount: int, currency: str) -> bool:
        """Set one package price in memory. Returns False on bad input."""
        if tokens_b not in (1, 5, 10) or currency not in ("BDT", "USDT"):
            return False
        if amount <= 0:
            return False
        attr = {
            (1, "BDT"): "price_1b",
            (5, "BDT"): "price_5b",
            (10, "BDT"): "price_10b",
            (1, "USDT"): "price_1b_usdt",
            (5, "USDT"): "price_5b_usdt",
            (10, "USDT"): "price_10b_usdt",
        }[(tokens_b, currency)]
        setattr(self, attr, amount)
        return True

    def apply_overrides(self, overrides: dict[str, str]) -> None:
        """Apply admin-set price overrides (from the DB) over env values.

        Keys are the PRICE_* env var names; bad values are ignored.
        """
        for (tokens_b, currency), key in self.PRICE_KEYS.items():
            raw = overrides.get(key)
            if raw is None:
                continue
            try:
                self.set_price(tokens_b, int(raw), currency)
            except ValueError:
                continue

    # -- helpers ---------------------------------------------------------
    @property
    def packages(self) -> list[tuple[int, int, str]]:
        """Bangladesh packages as (tokens_in_billions, amount, currency)."""
        return [
            (1, self.price_1b, "BDT"),
            (5, self.price_5b, "BDT"),
            (10, self.price_10b, "BDT"),
        ]

    def packages_for_region(self, region: str) -> list[tuple[int, int, str]]:
        """Packages for a region: BDT prices for 'bd', USDT for 'global'."""
        if region == "bd":
            return self.packages
        return [
            (1, self.price_1b_usdt, "USDT"),
            (5, self.price_5b_usdt, "USDT"),
            (10, self.price_10b_usdt, "USDT"),
        ]

    def price_for(self, tokens_b: int, region: str = "bd") -> tuple[int, str] | None:
        for tokens, amount, currency in self.packages_for_region(region):
            if tokens == tokens_b:
                return amount, currency
        return None

    def payment_methods_for_region(self, region: str) -> list[str]:
        """Bangladesh: bKash + Nagad + Binance. Global: Binance only."""
        if region == "bd":
            return ["bkash", "nagad", "binance"]
        return ["binance"]

    def payment_address(self, method: str) -> str:
        return {
            "bkash": self.bkash_number,
            "nagad": self.nagad_number,
            "binance": self.binance_pay_id,
        }.get(method, "")

    def validate(self) -> list[str]:
        """Return the names of required env vars that are missing.

        Only the bot token, the KeyCraft key and the admin id are fatal.
        A missing payment number only hides that payment method (and is
        logged as a warning at startup).
        """
        missing: list[str] = []
        if not self.telegram_bot_token:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not self.keycraft_api_key:
            missing.append("KEYCRAFT_API_KEY")
        if not self.admin_telegram_id:
            missing.append("ADMIN_TELEGRAM_ID")
        return missing

    def payment_warnings(self) -> list[str]:
        """Names of payment details that are not configured."""
        warnings: list[str] = []
        if not self.bkash_number:
            warnings.append("BKASH_NUMBER")
        if not self.nagad_number:
            warnings.append("NAGAD_NUMBER")
        if not self.binance_pay_id:
            warnings.append("BINANCE_PAY_ID")
        return warnings
