"""Offline tests for the supplier layer and storage.

No real network calls: KeyCraft is tested through httpx.MockTransport,
so these tests run anywhere with `python -m unittest discover -s tests -v`.
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

from storage import OrderStore
from suppliers.base import SupplierError
from suppliers.keycraft import KeyCraftSupplier
from suppliers.router import SupplierRouter


def make_transport(*, rate=0.06, balance=10.0, stock="IN_STOCK",
                   maintenance=False, place_status=200, calls=None):
    """A fake KeyCraft server. `calls` records every POST /reseller/orders."""
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/reseller/status"):
            return httpx.Response(200, json={
                "stock": stock, "maintenance": maintenance})
        if path.endswith("/reseller/balance"):
            return httpx.Response(200, json={
                "balance_usd": balance, "rate_per_1b": rate,
                "lifetime_usage_usd": 1.5})
        if path.endswith("/reseller/orders/quote"):
            return httpx.Response(200, json={"estimated_cost": 0.06})
        if path.endswith("/reseller/orders") and request.method == "POST":
            if calls is not None:
                calls.append(json.loads(request.content.decode()))
            if place_status != 200:
                return httpx.Response(place_status, json={"error": "fail"})
            body = json.loads(request.content.decode())
            return httpx.Response(200, json={
                "order_id": "kc-order-1", "invite_code": body["invite_code"],
                "status": "COMPLETED", "target_tokens_b": body["tokens_b"],
                "delivered_tokens_b": body["tokens_b"],
                "progress_percent": 100.0, "total_cost": 0.06,
                "refunded_amount": 0.0})
        if "/reseller/orders/" in path:
            return httpx.Response(200, json={
                "order_id": "kc-order-1", "status": "COMPLETED",
                "target_tokens_b": 1, "delivered_tokens_b": 1,
                "progress_percent": 100.0, "refunded_amount": 0.0})
        return httpx.Response(404, json={"error": "not found"})
    return httpx.MockTransport(handler)


def make_supplier(name="keycraft", **kwargs):
    calls = kwargs.pop("calls", None)
    supplier = KeyCraftSupplier(
        api_key="test-key",
        transport=make_transport(calls=calls, **kwargs),
    )
    supplier.name = name
    return supplier


class KeyCraftTest(unittest.IsolatedAsyncioTestCase):
    async def test_status_and_balance(self):
        supplier = make_supplier(rate=0.06, balance=2.0)
        status = await supplier.check_stock()
        self.assertEqual(status["stock"], "IN_STOCK")
        self.assertFalse(status["maintenance"])
        balance = await supplier.get_balance()
        self.assertEqual(balance["balance_usd"], 2.0)
        self.assertEqual(balance["rate_per_1b"], 0.06)
        await supplier.close()

    async def test_place_order_success(self):
        supplier = make_supplier()
        order = await supplier.place_order("TCJLWV", 1, "KC-TEST1")
        self.assertEqual(order["status"], "COMPLETED")
        self.assertEqual(order["delivered_tokens_b"], 1)
        await supplier.close()

    async def test_insufficient_balance_402(self):
        supplier = make_supplier(place_status=402)
        with self.assertRaises(SupplierError) as ctx:
            await supplier.place_order("TCJLWV", 1, "KC-TEST2")
        self.assertEqual(ctx.exception.status_code, 402)
        await supplier.close()

    async def test_out_of_stock_409(self):
        supplier = make_supplier(place_status=409)
        with self.assertRaises(SupplierError) as ctx:
            await supplier.place_order("TCJLWV", 1, "KC-TEST3")
        self.assertEqual(ctx.exception.status_code, 409)
        await supplier.close()


def make_live_transport():
    """A fake KeyCraft server returning the EXACT live JSON shapes,
    verified 2026-11-25 via the real API (see normalize_status docstring).
    Regression test: the live /reseller/status says "AVAILABLE", not
    "IN_STOCK" — the router must still treat the pool as available.
    """
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/reseller/status"):
            return httpx.Response(200, json={
                "service": "MuseAI Token Boost",
                "maintenance": False,
                "maintenance_message": None,
                "in_stock": True,
                "stock_status": "AVAILABLE",
                "price_per_b": 0.06,
                "min_tokens_b": 1,
                "max_tokens_b": 30,
                "max_bulk_codes": 10})
        if path.endswith("/reseller/balance"):
            return httpx.Response(200, json={
                "reseller_id": "efffd4d6-935b-40df-94bb-98aa283ee80e",
                "name": "Md", "balance": 2.0, "currency": "USD",
                "price_per_b": 0.06, "total_spent": 0.0,
                "total_tokens_b": 0, "is_active": True})
        return httpx.Response(404, json={"error": "not found"})
    return httpx.MockTransport(handler)


class LiveResponseTest(unittest.IsolatedAsyncioTestCase):
    async def test_live_available_shape_is_in_stock(self):
        supplier = KeyCraftSupplier(
            api_key="test-key", transport=make_live_transport())
        status = await supplier.check_stock()
        self.assertEqual(status["stock"], "IN_STOCK")
        self.assertFalse(status["maintenance"])
        balance = await supplier.get_balance()
        self.assertEqual(balance["balance_usd"], 2.0)
        self.assertEqual(balance["rate_per_1b"], 0.06)
        await supplier.close()

    async def test_live_shape_makes_packages_available(self):
        supplier = KeyCraftSupplier(
            api_key="test-key", transport=make_live_transport())
        router = SupplierRouter([supplier])
        for tokens_b in (1, 5, 10, 30):
            ok, reason = await router.check_availability(tokens_b)
            self.assertTrue(ok, f"{tokens_b}B should be available")
            self.assertIsNone(reason)
        await router.close()


class RouterTest(unittest.IsolatedAsyncioTestCase):
    async def test_picks_cheapest(self):
        cheap_calls, expensive_calls = [], []
        cheap = make_supplier("cheap", rate=0.05, calls=cheap_calls)
        expensive = make_supplier("expensive", rate=0.06, calls=expensive_calls)
        router = SupplierRouter([expensive, cheap])  # order shuffled on purpose
        name, order = await router.place_order("TCJLWV", 1, "KC-CHEAP")
        self.assertEqual(name, "cheap")
        self.assertEqual(order["status"], "COMPLETED")
        self.assertEqual(len(cheap_calls), 1)
        self.assertEqual(len(expensive_calls), 0)
        await router.close()

    async def test_fallback_when_cheapest_fails(self):
        cheap_calls, fallback_calls = [], []
        cheap = make_supplier("cheap", rate=0.05, place_status=402,
                              calls=cheap_calls)
        fallback = make_supplier("fallback", rate=0.07, calls=fallback_calls)
        router = SupplierRouter([cheap, fallback])
        name, order = await router.place_order("TCJLWV", 1, "KC-FALLBACK")
        self.assertEqual(name, "fallback")
        self.assertEqual(order["status"], "COMPLETED")
        self.assertEqual(len(cheap_calls), 1)
        self.assertEqual(len(fallback_calls), 1)
        await router.close()

    async def test_skips_supplier_without_enough_balance(self):
        poor_calls, rich_calls = [], []
        poor = make_supplier("poor", rate=0.06, balance=0.01, calls=poor_calls)
        rich = make_supplier("rich", rate=0.06, balance=10.0, calls=rich_calls)
        router = SupplierRouter([poor, rich])
        name, _ = await router.place_order("TCJLWV", 1, "KC-RICH")
        self.assertEqual(name, "rich")
        self.assertEqual(len(poor_calls), 0)
        await router.close()

    async def test_no_eligible_supplier(self):
        empty = make_supplier("empty", stock="OUT_OF_STOCK")
        router = SupplierRouter([empty])
        ok, reason = await router.check_availability(1)
        self.assertFalse(ok)
        self.assertEqual(reason, "out_of_stock")
        with self.assertRaises(SupplierError):
            await router.place_order("TCJLWV", 1, "KC-NONE")
        await router.close()


class StorageTest(unittest.TestCase):
    def test_order_and_region_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = OrderStore(os.path.join(tmp, "test.db"))
            store.set_user_region(111, "bd")
            self.assertEqual(store.get_user_region(111), "bd")
            self.assertIsNone(store.get_user_region(999))

            order = store.create_order(
                order_id="KC-TEST9", user_id=111, username="@test",
                region="bd", tokens_b=1, price_amount=100, currency="BDT",
                payment_method="bkash", trx_id="9X7A12BC84",
                invite_code="TCJLWV",
            )
            self.assertEqual(order["status"], "PENDING")
            self.assertEqual(order["supplier"], "keycraft")
            self.assertEqual(len(store.list_orders(status="PENDING")), 1)
            updated = store.update_status(
                "KC-TEST9", "APPROVED",
                keycraft_order_id="kc-1", supplier="keycraft",
            )
            self.assertEqual(updated["status"], "APPROVED")
            self.assertEqual(updated["keycraft_order_id"], "kc-1")
            self.assertEqual(store.list_orders(status="PENDING"), [])

    def test_settings_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = OrderStore(os.path.join(tmp, "test.db"))
            self.assertIsNone(store.get_setting("PRICE_1B"))
            self.assertEqual(store.get_all_settings(), {})
            store.set_setting("PRICE_1B", "120")
            self.assertEqual(store.get_setting("PRICE_1B"), "120")
            store.set_setting("PRICE_1B", "150")
            self.assertEqual(store.get_setting("PRICE_1B"), "150")
            self.assertEqual(
                store.get_all_settings(), {"PRICE_1B": "150"})


class PriceOverrideTest(unittest.TestCase):
    def test_set_price_and_overrides(self):
        from config import Settings
        settings = Settings()
        self.assertEqual(settings.price_1b, 30)
        self.assertTrue(settings.set_price(1, 120, "BDT"))
        self.assertEqual(settings.price_1b, 120)
        self.assertEqual(settings.price_for(1, "bd"), (120, "BDT"))
        # The 30B bulk package works the same way.
        self.assertTrue(settings.set_price(30, 900, "BDT"))
        self.assertEqual(settings.price_30b, 900)
        self.assertEqual(settings.price_for(30, "bd"), (900, "BDT"))
        self.assertEqual(settings.price_for(30, "global"), (21, "USDT"))
        # Bad inputs are rejected and leave the price unchanged.
        self.assertFalse(settings.set_price(2, 120, "BDT"))
        self.assertFalse(settings.set_price(1, 0, "BDT"))
        self.assertFalse(settings.set_price(1, -5, "BDT"))
        self.assertFalse(settings.set_price(1, 120, "USD"))
        self.assertEqual(settings.price_1b, 120)

    def test_apply_overrides_from_db(self):
        from config import Settings
        with tempfile.TemporaryDirectory() as tmp:
            store = OrderStore(os.path.join(tmp, "test.db"))
            store.set_setting("PRICE_1B", "120")
            store.set_setting("PRICE_5B_USDT", "5")
            store.set_setting("PRICE_30B", "900")
            store.set_setting("PRICE_1B_USDT", "not-a-number")
            settings = Settings()
            settings.apply_overrides(store.get_all_settings())
            self.assertEqual(settings.price_1b, 120)
            self.assertEqual(settings.price_5b_usdt, 5)
            self.assertEqual(settings.price_30b, 900)
            self.assertEqual(settings.price_1b_usdt, 1)  # bad value ignored
            self.assertEqual(settings.price_5b, 150)  # untouched stays default


if __name__ == "__main__":
    unittest.main()
