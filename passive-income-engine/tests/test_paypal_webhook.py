import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

_tmp = tempfile.TemporaryDirectory()
os.environ.setdefault("DATABASE_PATH", str(Path(_tmp.name) / "paypal-webhook-test.db"))
os.environ.setdefault("ADMIN_TOKEN", "test-admin-token")
os.environ.setdefault("WEBHOOK_SECRET", "test-webhook-secret")
os.environ.setdefault("PUBLIC_BASE_URL", "http://testserver")
os.environ.setdefault("CURRENCY", "CAD")
os.environ.setdefault("PROFIT_FLOOR_CENTS", "50000")
os.environ.setdefault("MIN_SWEEP_CENTS", "5000")
os.environ.setdefault("MAX_SWEEP_CENTS", "100000")
os.environ.setdefault("TAX_RESERVE_BPS", "2500")
os.environ.setdefault("REFUND_RESERVE_BPS", "500")
os.environ.setdefault("OPERATING_RESERVE_CENTS", "10000")
os.environ.setdefault("MAX_DOWNLOADS", "2")
os.environ.setdefault("PAYPAL_MODE", "sandbox")
os.environ.setdefault("PAYPAL_CLIENT_ID", "")
os.environ.setdefault("PAYPAL_CLIENT_SECRET", "")
os.environ.setdefault("PAYPAL_WEBHOOK_ID", "WH-TEST")

from fastapi.testclient import TestClient

import checkout_app
import engine


class PayPalWebhookTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(checkout_app.app)
        with engine.db() as con:
            for table in ("paypal_events", "refunds", "sales"):
                con.execute(f"DELETE FROM {table}")
            con.execute(
                "INSERT INTO sales(id,product_id,net_cents,currency,created_at) VALUES(?,?,?,?,?)",
                (
                    "CAPTURE-REFUND-1",
                    "compound-growth-calculator",
                    855,
                    engine.CURRENCY,
                    engine.utcnow(),
                ),
            )

    @staticmethod
    def _refund_event(currency: str) -> dict:
        return {
            "id": "WH-EVENT-REFUND-1",
            "event_type": "PAYMENT.CAPTURE.REFUNDED",
            "resource": {
                "id": "REFUND-1",
                "amount": {"currency_code": currency, "value": "9.00"},
                "supplementary_data": {
                    "related_ids": {"capture_id": "CAPTURE-REFUND-1"}
                },
            },
        }

    def test_invalid_refund_does_not_poison_retry_deduplication(self):
        verifier = AsyncMock(return_value=True)
        with patch.object(checkout_app, "_verify_paypal_webhook", verifier):
            invalid = self.client.post(
                "/webhooks/paypal",
                content=json.dumps(self._refund_event("USD")),
                headers={"content-type": "application/json"},
            )
            self.assertEqual(invalid.status_code, 409)

            with engine.db() as con:
                event_count = con.execute(
                    "SELECT COUNT(*) AS n FROM paypal_events WHERE event_id=?",
                    ("WH-EVENT-REFUND-1",),
                ).fetchone()["n"]
                refund_count = con.execute(
                    "SELECT COUNT(*) AS n FROM refunds WHERE id=?",
                    ("REFUND-1",),
                ).fetchone()["n"]
            self.assertEqual(event_count, 0)
            self.assertEqual(refund_count, 0)

            retry = self.client.post(
                "/webhooks/paypal",
                content=json.dumps(self._refund_event("CAD")),
                headers={"content-type": "application/json"},
            )
            self.assertEqual(retry.status_code, 200)
            self.assertEqual(retry.json()["status"], "ok")

        with engine.db() as con:
            event_count = con.execute(
                "SELECT COUNT(*) AS n FROM paypal_events WHERE event_id=?",
                ("WH-EVENT-REFUND-1",),
            ).fetchone()["n"]
            refund = con.execute(
                "SELECT amount_cents,currency,sale_id,product_id FROM refunds WHERE id=?",
                ("REFUND-1",),
            ).fetchone()
        self.assertEqual(event_count, 1)
        self.assertIsNotNone(refund)
        self.assertEqual(refund["amount_cents"], 900)
        self.assertEqual(refund["currency"], "CAD")
        self.assertEqual(refund["sale_id"], "CAPTURE-REFUND-1")
        self.assertEqual(refund["product_id"], "compound-growth-calculator")


if __name__ == "__main__":
    unittest.main()
