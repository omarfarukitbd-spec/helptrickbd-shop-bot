"""Order + user storage in a small local SQLite database (orders.db).

One connection per operation (cheap at this volume, avoids any
thread/async sharing problems).

Orders flow: PENDING -> APPROVED -> COMPLETED | PARTIAL | FAILED,
or PENDING -> REJECTED.
Users table remembers each user's region choice ("bd" or "global").
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    username TEXT,
    region TEXT NOT NULL DEFAULT 'global',
    tokens_b INTEGER NOT NULL,
    price_amount INTEGER NOT NULL,
    currency TEXT NOT NULL DEFAULT 'BDT',
    payment_method TEXT NOT NULL,
    trx_id TEXT NOT NULL,
    invite_code TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    supplier TEXT NOT NULL DEFAULT 'keycraft',
    keycraft_order_id TEXT,
    delivered_b REAL,
    refunded_usd REAL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    region TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Admin-set overrides (e.g. package prices changed with /setprice).
-- Key/value so the bot survives restarts without touching env vars.
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class OrderStore:
    def __init__(self, db_path: str = "orders.db") -> None:
        self.db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    # -- users: saved region choice ---------------------------------------
    def set_user_region(self, user_id: int, region: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO users (user_id, region, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE
                SET region = excluded.region, updated_at = excluded.updated_at
                """,
                (user_id, region, _now()),
            )

    def get_user_region(self, user_id: int) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT region FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
        return row["region"] if row else None

    # -- settings: admin overrides (e.g. /setprice) -----------------------
    def set_setting(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE
                SET value = excluded.value, updated_at = excluded.updated_at
                """,
                (key, value, _now()),
            )

    def get_setting(self, key: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
        return row["value"] if row else None

    def get_all_settings(self) -> dict[str, str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {row["key"]: row["value"] for row in rows}

    # -- orders: writes ----------------------------------------------------
    def create_order(
        self,
        order_id: str,
        user_id: int,
        username: str | None,
        region: str,
        tokens_b: int,
        price_amount: int,
        currency: str,
        payment_method: str,
        trx_id: str,
        invite_code: str,
        supplier: str = "keycraft",
    ) -> dict:
        now = _now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO orders
                (order_id, user_id, username, region, tokens_b, price_amount,
                 currency, payment_method, trx_id, invite_code, status,
                 supplier, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?, ?)
                """,
                (
                    order_id, user_id, username, region, tokens_b, price_amount,
                    currency, payment_method, trx_id, invite_code,
                    supplier, now, now,
                ),
            )
        return self.get_order(order_id)

    def update_status(
        self,
        order_id: str,
        status: str,
        keycraft_order_id: str | None = None,
        delivered_b: float | None = None,
        refunded_usd: float | None = None,
        supplier: str | None = None,
    ) -> dict | None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE orders
                SET status = ?,
                    keycraft_order_id = COALESCE(?, keycraft_order_id),
                    delivered_b = COALESCE(?, delivered_b),
                    refunded_usd = COALESCE(?, refunded_usd),
                    supplier = COALESCE(?, supplier),
                    updated_at = ?
                WHERE order_id = ?
                """,
                (
                    status, keycraft_order_id, delivered_b,
                    refunded_usd, supplier, _now(), order_id,
                ),
            )
        return self.get_order(order_id)

    # -- orders: reads ------------------------------------------------------
    def get_order(self, order_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM orders WHERE order_id = ?", (order_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_orders(self, status: str | None = None, limit: int = 20) -> list[dict]:
        with self._connect() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM orders WHERE status = ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM orders ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(row) for row in rows]
