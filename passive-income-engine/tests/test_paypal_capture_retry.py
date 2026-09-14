import os
import tempfile
import unittest
from pathlib import Path

_tmp = tempfile.TemporaryDirectory()
os.environ.setdefault("DATABASE_PATH", str(Path(_tmp.name) / "bootstrap.db"))
os.environ.setdefault("ADMIN_TOKEN", "test-admin-token")
os.environ.setdefault("WEBHOOK_SECRET", "test-webhook-secret")
os.environ.setdefault("PUBLIC_BASE_URL", "http://testserver")
os.environ.setdefault("CURRENCY", "CAD")
os.environ.setdefault("PAYPAL_MODE", "sandbox")
os.environ.setdefault("PAYPAL_CLIENT_ID", "")
os.environ.setdefault("PAYPAL_CLIENT_SECRET", "")
os.environ.setdefault("PAYPAL_WEBHOOK_ID", "")

from fastapi.testclient import TestClient

import checkout_app
import engine


class PayPalCaptureRetryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_database_path = engine.DATABASE_PATH
        self.original_max_downloads = engine.MAX_DOWNLOADS
        engine.DATABASE_PATH = str(Path(self.temp_dir.name) / "test.db")
        engine.MAX_DOWNLOADS = 2
        engine.init_db()
        checkout_app._init_paypal_tables()
        self.client = TestClient(checkout_app.app)

    def tearDown(self):
        engine.DATABASE_PATH = self.original_database_path
        engine.MAX_DOWNLOADS = self.original_max_downloads
        self.temp_dir.cleanup()

    @staticmethod
    def paypal_order_fixture():
        return {
            "id": "ORDER-RETRY",
            "status": "COMPLETED",
            "purchase_units": [{
                "reference_id": "compound-growth-calculator",
                "custom_id": "compound-growth-calculator",
                "payments": {"captures": [{
                    "id": "CAPTURE-RETRY",
                    "status": "COMPLETED",
                    "amount": {"currency_code": "CAD", "value": "9.00"},
                    "seller_receivable_breakdown": {
                        "net_amount": {"currency_code": "CAD", "value": "8.55"},
                        "paypal_fee": {"currency_code": "CAD", "value": "0.45"},
                    },
                }]},
            }],
        }

    def test_capture_retry_preserves_consumed_download_quota(self):
        with engine.db() as con:
            con.execute(
                "INSERT INTO paypal_orders(order_id,product_id,visitor_hash,status,created_at) VALUES(?,?,?,?,?)",
                ("ORDER-RETRY", "compound-growth-calculator", "visitor-hash", "CREATED", engine.utcnow()),
            )

        order = self.paypal_order_fixture()
        capture = checkout_app._capture_from_order(order)
        first_token = checkout_app.fulfill_paypal_capture("ORDER-RETRY", order, capture)
        self.assertEqual(self.client.get(f"/download/{first_token}").status_code, 200)

        second_token = checkout_app.fulfill_paypal_capture("ORDER-RETRY", order, capture)
        self.assertNotEqual(first_token, second_token)

        with engine.db() as con:
            delivery = con.execute(
                "SELECT downloads FROM deliveries WHERE sale_id='CAPTURE-RETRY'"
            ).fetchone()
        self.assertEqual(delivery["downloads"], 1)

        self.assertEqual(self.client.get(f"/download/{first_token}").status_code, 404)
        self.assertEqual(self.client.get(f"/download/{second_token}").status_code, 200)
        self.assertEqual(self.client.get(f"/download/{second_token}").status_code, 404)


if __name__ == "__main__":
    unittest.main()
