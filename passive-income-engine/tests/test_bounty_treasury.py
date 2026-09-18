import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


SCRIPT = textwrap.dedent(
    """
    import json
    import engine

    engine.init_db()
    with engine.db() as con:
        con.execute(
            '''
            INSERT INTO bounty_earnings(
              source,external_id,settlement_ref,gross_cents,fees_cents,net_cents,currency,created_at
            ) VALUES(?,?,?,?,?,?,?,?)
            ''',
            (
                "opentask",
                "task-1",
                "receipt-1",
                int(__import__("os").environ["TEST_GROSS_CENTS"]),
                int(__import__("os").environ["TEST_FEES_CENTS"]),
                int(__import__("os").environ["TEST_NET_CENTS"]),
                __import__("os").environ["TEST_SETTLEMENT_CURRENCY"],
                engine.utcnow(),
            ),
        )
    print(json.dumps(engine.treasury().__dict__, sort_keys=True))
    """
)


class BountyTreasuryIntegrationTests(unittest.TestCase):
    def run_snapshot(self, settlement_currency: str) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env.update(
                {
                    "DATABASE_PATH": str(Path(tmp) / "engine.db"),
                    "CURRENCY": "CAD",
                    "PROFIT_FLOOR_CENTS": "10000",
                    "MIN_SWEEP_CENTS": "1000",
                    "MAX_SWEEP_CENTS": "100000",
                    "TAX_RESERVE_BPS": "2500",
                    "REFUND_RESERVE_BPS": "0",
                    "OPERATING_RESERVE_CENTS": "5000",
                    "TEST_GROSS_CENTS": "100000" if settlement_currency == "CAD" else "10000",
                    "TEST_FEES_CENTS": "4500" if settlement_currency == "CAD" else "450",
                    "TEST_NET_CENTS": "95500" if settlement_currency == "CAD" else "9550",
                    "TEST_SETTLEMENT_CURRENCY": settlement_currency,
                }
            )
            proc = subprocess.run(
                [sys.executable, "-c", SCRIPT],
                cwd=str(Path(__file__).resolve().parents[1]),
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            return json.loads(proc.stdout.strip().splitlines()[-1])

    def test_same_currency_bounty_income_flows_into_treasury(self):
        snapshot = self.run_snapshot("CAD")
        self.assertEqual(snapshot["sales_cents"], 0)
        self.assertEqual(snapshot["bounty_income_cents"], 95_500)
        self.assertEqual(snapshot["tax_reserve_cents"], 23_875)
        self.assertEqual(snapshot["payout_ready_cents"], 56_625)

    def test_foreign_currency_bounty_is_not_mixed_into_cad_treasury(self):
        snapshot = self.run_snapshot("USDC")
        self.assertEqual(snapshot["bounty_income_cents"], 0)
        self.assertEqual(snapshot["payout_ready_cents"], 0)


if __name__ == "__main__":
    unittest.main()
