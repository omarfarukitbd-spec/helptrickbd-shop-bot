"""Cheapest-supplier routing.

Rule (user's standing rule): when an order comes in, the bot compares the
LIVE rate per 1B tokens across all configured suppliers, keeps only the
suppliers that are IN_STOCK and have enough wallet balance for the order,
and places the order with the CHEAPEST one. If the cheapest fails
(out of stock / insufficient balance / maintenance / rate limited),
it automatically falls back to the next cheapest.

Each supplier has its OWN separate wallet. The bot never moves money
between suppliers — it only spends from the chosen supplier's wallet.

Fallback only happens on errors that prove the order was NOT placed
(402 insufficient balance, 409 out of stock, 503 maintenance,
429 rate limited). Ambiguous errors (e.g. a network timeout after the
request was sent — the order may or may not exist) are NOT retried on
another supplier, because that could double-deliver tokens.
"""

from __future__ import annotations

import logging

from .base import Supplier, SupplierError

logger = logging.getLogger(__name__)

# Errors that definitely mean "this supplier did not place the order",
# so trying the next cheapest supplier is safe.
RETRYABLE_STATUS_CODES = {402, 409, 503, 429}

# Stock states that still have tokens available.
AVAILABLE_STOCK = {"IN_STOCK", "LOW_STOCK"}


class SupplierRouter:
    """Routes orders to the cheapest eligible supplier, with fallback."""

    def __init__(self, suppliers: list[Supplier]) -> None:
        self.suppliers = list(suppliers)

    async def close(self) -> None:
        for supplier in self.suppliers:
            await supplier.close()

    async def __aenter__(self) -> "SupplierRouter":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    # -- eligibility ---------------------------------------------------------
    async def eligible_suppliers(self, tokens_b: int) -> list[dict]:
        """Suppliers that can fulfil this order, cheapest first.

        Each entry: {"supplier", "rate_per_1b", "balance_usd", "stock"}.
        A supplier is eligible when it is in stock (IN_STOCK / LOW_STOCK),
        not in maintenance, and its wallet covers tokens_b at its live rate.
        Suppliers that error on the live checks are skipped (and logged).
        """
        candidates: list[dict] = []
        for supplier in self.suppliers:
            try:
                stock = await supplier.check_stock()
                if stock.get("maintenance") or stock.get("stock") not in AVAILABLE_STOCK:
                    continue
                balance = await supplier.get_balance()
                rate = balance["rate_per_1b"]
                cost = tokens_b * rate
                if balance["balance_usd"] < cost:
                    logger.info(
                        "%s skipped: balance $%.2f < cost $%.2f",
                        supplier.name, balance["balance_usd"], cost,
                    )
                    continue
                candidates.append(
                    {
                        "supplier": supplier,
                        "rate_per_1b": rate,
                        "balance_usd": balance["balance_usd"],
                        "stock": stock["stock"],
                    }
                )
            except SupplierError as exc:
                logger.warning("%s live check failed, skipping: %s",
                               supplier.name, exc)
        candidates.sort(key=lambda c: c["rate_per_1b"])
        return candidates

    async def check_availability(self, tokens_b: int) -> tuple[bool, str | None]:
        """Can ANY supplier fulfil this order right now?

        Returns (True, None) or (False, reason_key) where reason_key is
        one of "maintenance" / "out_of_stock" / "temporarily_unavailable"
        (keys in strings.py).
        """
        if not self.suppliers:
            return False, "temporarily_unavailable"

        saw_maintenance = False
        saw_out_of_stock = False
        for supplier in self.suppliers:
            try:
                stock = await supplier.check_stock()
            except SupplierError:
                continue
            if stock.get("maintenance"):
                saw_maintenance = True
            elif stock.get("stock") == "OUT_OF_STOCK":
                saw_out_of_stock = True

        if await self.eligible_suppliers(tokens_b):
            return True, None
        if saw_maintenance:
            return False, "maintenance"
        if saw_out_of_stock:
            return False, "out_of_stock"
        return False, "temporarily_unavailable"

    # -- ordering --------------------------------------------------------------
    async def place_order(
        self, invite_code: str, tokens_b: int, external_order_id: str
    ) -> tuple[str, dict]:
        """Place the order with the cheapest eligible supplier.

        Returns (supplier_name, normalized_order). Falls back to the next
        cheapest supplier on retryable failures. Raises SupplierError if
        no supplier can fulfil the order.
        """
        candidates = await self.eligible_suppliers(tokens_b)
        if not candidates:
            raise SupplierError(
                "No supplier can fulfil this order right now."
            )

        errors: list[str] = []
        for candidate in candidates:
            supplier = candidate["supplier"]
            try:
                order = await supplier.place_order(
                    invite_code, tokens_b, external_order_id
                )
                logger.info(
                    "Order %s placed via %s at $%.2f/1B",
                    external_order_id, supplier.name,
                    candidate["rate_per_1b"],
                )
                return supplier.name, order
            except SupplierError as exc:
                errors.append(f"{supplier.name}: {exc.message}")
                if exc.status_code in RETRYABLE_STATUS_CODES:
                    logger.warning(
                        "%s failed (%s), falling back to next supplier",
                        supplier.name, exc.message,
                    )
                    continue
                # Ambiguous failure — do NOT try another supplier.
                raise SupplierError(
                    f"{supplier.name} failed: {exc.message}",
                    status_code=exc.status_code,
                ) from exc

        raise SupplierError(
            "All suppliers failed: " + "; ".join(errors)
        )

    async def get_order_status(self, supplier_name: str, order_id: str) -> dict:
        """Live progress of an order, from the supplier that placed it."""
        for supplier in self.suppliers:
            if supplier.name == supplier_name:
                return await supplier.get_order_status(order_id)
        raise SupplierError(f"Unknown supplier: {supplier_name}")
