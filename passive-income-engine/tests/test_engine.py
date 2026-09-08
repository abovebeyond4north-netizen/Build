import hashlib
import hmac
import json
import os
import tempfile
import unittest
from pathlib import Path

_tmp = tempfile.TemporaryDirectory()
os.environ["DATABASE_PATH"] = str(Path(_tmp.name) / "test.db")
os.environ["ADMIN_TOKEN"] = "test-admin-token"
os.environ["WEBHOOK_SECRET"] = "test-webhook-secret"
os.environ["PUBLIC_BASE_URL"] = "http://testserver"
os.environ["CURRENCY"] = "CAD"
os.environ["PROFIT_FLOOR_CENTS"] = "50000"
os.environ["MIN_SWEEP_CENTS"] = "5000"
os.environ["MAX_SWEEP_CENTS"] = "100000"
os.environ["TAX_RESERVE_BPS"] = "2500"
os.environ["REFUND_RESERVE_BPS"] = "500"
os.environ["OPERATING_RESERVE_CENTS"] = "10000"
os.environ["MAX_DOWNLOADS"] = "2"

from fastapi.testclient import TestClient
import engine


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(engine.app)
        with engine.db() as con:
            for table in (
                "sale_attribution",
                "visitor_sessions",
                "product_views",
                "audit_log",
                "events",
                "deliveries",
                "refunds",
                "sales",
                "expenses",
            ):
                con.execute(f"DELETE FROM {table}")

    def signed_post(self, payload: dict):
        raw = json.dumps(payload, separators=(",", ":")).encode()
        signature = hmac.new(b"test-webhook-secret", raw, hashlib.sha256).hexdigest()
        return self.client.post(
            "/webhooks/payment",
            content=raw,
            headers={"x-signature": signature, "content-type": "application/json"},
        )

    def test_health_and_discovery_pages(self):
        self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertEqual(self.client.get("/sitemap.xml").status_code, 200)
        self.assertEqual(self.client.get("/robots.txt").status_code, 200)
        self.assertEqual(self.client.get("/feed.xml").status_code, 200)
        self.assertEqual(self.client.get("/guides").status_code, 200)

    def test_product_view_is_deduplicated_per_visitor_per_day(self):
        url = "/products/compound-growth-calculator?utm_source=search&utm_medium=organic&utm_campaign=evergreen"
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get(url).status_code, 200)
        with engine.db() as con:
            views = con.execute(
                "SELECT COUNT(*) v FROM product_views WHERE product_id='compound-growth-calculator'"
            ).fetchone()["v"]
        self.assertEqual(views, 1)

    def test_signed_sale_fulfills_and_attributes(self):
        self.client.get(
            "/products/compound-growth-calculator?utm_source=search&utm_medium=organic&utm_campaign=evergreen"
        )
        visitor = self.client.cookies.get("bdt_visitor")
        response = self.signed_post(
            {
                "id": "evt-sale-1",
                "type": "sale.completed",
                "sale_id": "sale-1",
                "product_id": "compound-growth-calculator",
                "gross_cents": 900,
                "net_cents": 855,
                "currency": "CAD",
                "visitor_id": visitor,
            }
        )
        self.assertEqual(response.status_code, 200)
        download_url = response.json()["download_url"]
        self.assertEqual(self.client.get(download_url).status_code, 200)
        self.assertEqual(self.client.get(download_url).status_code, 200)
        self.assertEqual(self.client.get(download_url).status_code, 404)

        admin = {"authorization": "Bearer test-admin-token"}
        attribution = self.client.get("/admin/attribution", headers=admin).json()["attribution"]
        self.assertEqual(attribution[0]["source"], "search")
        self.assertEqual(attribution[0]["medium"], "organic")

    def test_duplicate_webhook_event_is_idempotent(self):
        payload = {
            "id": "evt-duplicate",
            "type": "sale.completed",
            "sale_id": "sale-duplicate",
            "product_id": "compound-growth-calculator",
            "gross_cents": 900,
            "net_cents": 850,
            "currency": "CAD",
        }
        self.assertEqual(self.signed_post(payload).status_code, 200)
        second = self.signed_post(payload)
        self.assertEqual(second.json()["status"], "duplicate")
        with engine.db() as con:
            count = con.execute("SELECT COUNT(*) v FROM sales").fetchone()["v"]
        self.assertEqual(count, 1)

    def test_browser_cannot_override_catalog_price(self):
        response = self.signed_post(
            {
                "id": "evt-bad-price",
                "type": "sale.completed",
                "sale_id": "sale-bad-price",
                "product_id": "compound-growth-calculator",
                "gross_cents": 1,
                "net_cents": 1,
                "currency": "CAD",
            }
        )
        self.assertEqual(response.status_code, 409)

    def test_treasury_reserves_before_payout_ready(self):
        with engine.db() as con:
            con.execute(
                "INSERT INTO sales VALUES(?,?,?,?,?)",
                ("sale-large", "microbusiness-kpi-dashboard", 200000, "CAD", engine.utcnow()),
            )
        snapshot = engine.treasury()
        self.assertEqual(snapshot.tax_reserve_cents, 50000)
        self.assertEqual(snapshot.refund_reserve_cents, 10000)
        self.assertEqual(snapshot.payout_ready_cents, 80000)

    def test_optimizer_returns_all_products(self):
        admin = {"authorization": "Bearer test-admin-token"}
        response = self.client.get("/admin/optimizer", headers=admin)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["products"]), len(engine.PRODUCTS))
        self.assertIn(payload["featured_product_id"], engine.PRODUCTS)
        self.assertEqual(payload["policy"]["automatic_action"], "rotate featured placement only")


if __name__ == "__main__":
    unittest.main()
