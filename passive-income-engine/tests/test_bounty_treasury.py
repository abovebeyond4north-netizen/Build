import tempfile
import unittest
from pathlib import Path

import engine


class BountyTreasuryIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.old_path = engine.DATABASE_PATH
        self.old_currency = engine.CURRENCY
        self.old_floor = engine.PROFIT_FLOOR_CENTS
        self.old_min = engine.MIN_SWEEP_CENTS
        self.old_max = engine.MAX_SWEEP_CENTS
        self.old_tax = engine.TAX_RESERVE_BPS
        self.old_refund = engine.REFUND_RESERVE_BPS
        self.old_operating = engine.OPERATING_RESERVE_CENTS

        engine.DATABASE_PATH = str(Path(self.tmp.name) / "engine.db")
        engine.CURRENCY = "CAD"
        engine.PROFIT_FLOOR_CENTS = 10_000
        engine.MIN_SWEEP_CENTS = 1_000
        engine.MAX_SWEEP_CENTS = 100_000
        engine.TAX_RESERVE_BPS = 2_500
        engine.REFUND_RESERVE_BPS = 0
        engine.OPERATING_RESERVE_CENTS = 5_000
        engine.init_db()

    def tearDown(self):
        engine.DATABASE_PATH = self.old_path
        engine.CURRENCY = self.old_currency
        engine.PROFIT_FLOOR_CENTS = self.old_floor
        engine.MIN_SWEEP_CENTS = self.old_min
        engine.MAX_SWEEP_CENTS = self.old_max
        engine.TAX_RESERVE_BPS = self.old_tax
        engine.REFUND_RESERVE_BPS = self.old_refund
        engine.OPERATING_RESERVE_CENTS = self.old_operating

    def test_same_currency_bounty_income_flows_into_treasury(self):
        with engine.db() as con:
            con.execute(
                """
                INSERT INTO bounty_earnings(
                  source,external_id,settlement_ref,gross_cents,fees_cents,net_cents,currency,created_at
                ) VALUES(?,?,?,?,?,?,?,?)
                """,
                ("opentask", "task-1", "receipt-1", 100_000, 4_500, 95_500, "CAD", engine.utcnow()),
            )

        snapshot = engine.treasury()
        self.assertEqual(snapshot.sales_cents, 0)
        self.assertEqual(snapshot.bounty_income_cents, 95_500)
        self.assertEqual(snapshot.tax_reserve_cents, 23_875)
        self.assertEqual(snapshot.payout_ready_cents, 56_625)

    def test_foreign_currency_bounty_is_not_mixed_into_cad_treasury(self):
        with engine.db() as con:
            con.execute(
                """
                INSERT INTO bounty_earnings(
                  source,external_id,settlement_ref,gross_cents,fees_cents,net_cents,currency,created_at
                ) VALUES(?,?,?,?,?,?,?,?)
                """,
                ("opentask", "task-2", "receipt-usdc", 10_000, 450, 9_550, "USDC", engine.utcnow()),
            )

        snapshot = engine.treasury()
        self.assertEqual(snapshot.bounty_income_cents, 0)
        self.assertEqual(snapshot.payout_ready_cents, 0)


if __name__ == "__main__":
    unittest.main()
