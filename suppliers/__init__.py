"""Supplier package: pluggable token suppliers + cheapest routing.

Add a second supplier later by:
  1. Writing a Supplier subclass in suppliers/ (see base.py).
  2. Adding it in get_suppliers() below, guarded by its own API key env var.
The router (router.py) then compares live rates automatically — bot.py
does not need to change.
"""

from __future__ import annotations

from .base import Supplier, SupplierError
from .keycraft import KeyCraftSupplier
from .router import SupplierRouter

__all__ = [
    "Supplier",
    "SupplierError",
    "KeyCraftSupplier",
    "SupplierRouter",
    "get_suppliers",
    "get_router",
]


def get_suppliers(settings) -> list[Supplier]:
    """All configured suppliers. Only suppliers with an API key are added.

    KeyCraft is the only supplier today. Each supplier spends from its OWN
    wallet — money is never moved between suppliers.
    """
    suppliers: list[Supplier] = []
    if settings.keycraft_api_key:
        suppliers.append(
            KeyCraftSupplier(
                api_key=settings.keycraft_api_key,
                base_url=settings.keycraft_base_url,
            )
        )
    # Future supplier example:
    # if settings.second_api_key:
    #     suppliers.append(SecondSupplier(api_key=settings.second_api_key))
    return suppliers


def get_router(settings) -> SupplierRouter:
    """A router over all configured suppliers (cheapest-first ordering)."""
    return SupplierRouter(get_suppliers(settings))
