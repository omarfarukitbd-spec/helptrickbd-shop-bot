"""KeyCraft supplier — the first implementation of the Supplier interface.

Docs: https://enterpriceai.store/apidocs
Base URL: https://enterpriceai.store/api/v1
Auth: Bearer API key.

Endpoints used:
  GET  /reseller/status            stock + maintenance
  GET  /reseller/balance           USD wallet, rate per 1B, lifetime usage
  POST /reseller/orders/quote      free dry-run (not used by the bot yet)
  POST /reseller/orders            place order (idempotent)
  GET  /reseller/orders/{id}       live order progress

KeyCraft's exact JSON field names are not fully documented, so responses
are normalized defensively (see _pick()): several common key variants are
accepted. If a live response ever uses a new field name, only the
normalize_* helpers below need updating — bot.py stays untouched.
"""

from __future__ import annotations

import httpx

from .base import Supplier, SupplierError

# KeyCraft rate: $0.06 per 1B tokens (10B = $0.60). Fallback when the live
# /reseller/balance response carries no rate field.
DEFAULT_RATE_PER_1B = 0.06

# Backwards-compatible name; new code should catch SupplierError.
KeyCraftError = SupplierError


def _pick(data: dict, *names, default=None):
    """Return the first present, non-None value among the given key names."""
    for name in names:
        value = data.get(name)
        if value is not None:
            return value
    return default


def normalize_status(data: dict) -> dict:
    stock = str(
        _pick(data, "stock", "stock_status", "status", default="UNKNOWN")
    ).upper()
    maintenance = bool(
        _pick(data, "maintenance", "maintenance_mode", "in_maintenance",
              default=False)
    )
    return {"stock": stock, "maintenance": maintenance, "raw": data}


def normalize_balance(data: dict) -> dict:
    balance = _pick(
        data, "balance_usd", "balance", "usd_balance", "wallet_balance",
        default=0.0,
    )
    rate = _pick(
        data, "rate_per_1b", "rate", "unit_price", "price_per_1b",
        default=DEFAULT_RATE_PER_1B,
    )
    lifetime = _pick(
        data, "lifetime_usage_usd", "lifetime_usage", "total_spent_usd",
        "lifetime_spent", default=None,
    )
    return {
        "balance_usd": float(balance),
        "rate_per_1b": float(rate),
        "lifetime_usd": None if lifetime is None else float(lifetime),
        "raw": data,
    }


def normalize_order(data: dict) -> dict:
    return {
        "order_id": _pick(data, "order_id", "id", default=""),
        "invite_code": _pick(data, "invite_code", default=""),
        "status": str(_pick(data, "status", default="")).upper(),
        "target_tokens_b": _pick(data, "target_tokens_b", "tokens_b", default=0),
        "delivered_tokens_b": _pick(data, "delivered_tokens_b", default=0),
        "progress_percent": _pick(data, "progress_percent", default=0.0),
        "total_cost": _pick(data, "total_cost", default=0.0),
        "refunded_amount": _pick(data, "refunded_amount", default=0.0),
        "raw": data,
    }


class KeyCraftSupplier(Supplier):
    """KeyCraft Reseller API, behind the Supplier interface."""

    name = "keycraft"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://enterpriceai.store/api/v1",
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    # -- internals ---------------------------------------------------------
    async def _request(self, method: str, path: str, **kwargs) -> dict:
        try:
            response = await self._client.request(method, path, **kwargs)
        except httpx.RequestError as exc:
            raise SupplierError(f"Could not reach KeyCraft API: {exc}") from exc

        if response.status_code == 402:
            raise SupplierError(
                "Insufficient KeyCraft wallet balance.", status_code=402
            )
        if response.status_code == 409:
            raise SupplierError("Token pool is out of stock.", status_code=409)
        if response.status_code == 503:
            raise SupplierError(
                "KeyCraft token service is in maintenance.", status_code=503
            )
        if response.status_code == 429:
            raise SupplierError(
                "KeyCraft rate limit reached. Please try again shortly.",
                status_code=429,
            )
        if response.status_code >= 400:
            raise SupplierError(
                f"KeyCraft API error {response.status_code}: "
                f"{response.text[:200]}",
                status_code=response.status_code,
            )

        data = response.json()
        return data if isinstance(data, dict) else {"data": data}

    # -- Supplier interface -------------------------------------------------
    async def check_stock(self) -> dict:
        return normalize_status(await self._request("GET", "/reseller/status"))

    async def get_balance(self) -> dict:
        return normalize_balance(await self._request("GET", "/reseller/balance"))

    async def place_order(
        self, invite_code: str, tokens_b: int, external_order_id: str
    ) -> dict:
        return normalize_order(
            await self._request(
                "POST",
                "/reseller/orders",
                json={
                    "invite_code": invite_code,
                    "tokens_b": tokens_b,
                    "external_order_id": external_order_id,
                },
            )
        )

    async def get_order_status(self, order_id: str) -> dict:
        return normalize_order(
            await self._request("GET", f"/reseller/orders/{order_id}")
        )

    # -- KeyCraft-only helper ------------------------------------------------
    async def quote(self, invite_code: str, tokens_b: int) -> dict:
        """Free dry-run: estimated cost, without charging anything."""
        return await self._request(
            "POST",
            "/reseller/orders/quote",
            json={"invite_code": invite_code, "tokens_b": tokens_b},
        )
