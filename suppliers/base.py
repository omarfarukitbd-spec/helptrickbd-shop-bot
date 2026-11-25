"""Supplier interface — the bot talks to token suppliers only through this.

A supplier is any reseller API that can sell Muse tokens. KeyCraft is the
first (and currently only) implementation. To add a second supplier later:
  1. Write a new class in suppliers/ implementing this interface.
  2. Register it in suppliers/__init__.py's get_supplier().
Nothing in bot.py needs to change — it only uses these four methods.

All money is in USD; all token amounts are in billions (1B = 1,000,000,000).
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class SupplierError(Exception):
    """An error talking to a supplier (network, balance, stock, ...)."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class Supplier(ABC):
    """One token supplier behind a common interface."""

    name: str = "supplier"

    # -- interface ---------------------------------------------------------
    @abstractmethod
    async def check_stock(self) -> dict:
        """Live stock state.

        Returns: {"stock": "IN_STOCK" | "LOW_STOCK" | "OUT_OF_STOCK"
                          | "UNKNOWN",
                  "maintenance": bool}
        """
        raise NotImplementedError

    @abstractmethod
    async def get_balance(self) -> dict:
        """Wallet balance + rate.

        Returns: {"balance_usd": float,
                  "rate_per_1b": float,       # USD per 1B tokens
                  "lifetime_usd": float | None}
        """
        raise NotImplementedError

    @abstractmethod
    async def place_order(
        self, invite_code: str, tokens_b: int, external_order_id: str
    ) -> dict:
        """Buy tokens for an invite code (idempotent via external_order_id).

        Returns a normalized order:
        {"order_id": str, "invite_code": str,
         "status": "COMPLETED" | "RUNNING" | "PARTIAL" | ...,
         "target_tokens_b": int, "delivered_tokens_b": float,
         "progress_percent": float, "total_cost": float,
         "refunded_amount": float}
        """
        raise NotImplementedError

    @abstractmethod
    async def get_order_status(self, order_id: str) -> dict:
        """Live progress of one order. Same normalized order dict."""
        raise NotImplementedError

    # -- lifecycle ---------------------------------------------------------
    async def close(self) -> None:
        """Release resources (HTTP connections, ...). Default: nothing."""

    async def __aenter__(self) -> "Supplier":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()
