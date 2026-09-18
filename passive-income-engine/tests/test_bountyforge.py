import os
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from bountyforge import (
    Bounty,
    Config,
    Store,
    decide,
    normalize_opentask,
    parse_budget,
)


class BountyForgeTests(unittest.TestCase):
    def make_store(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db = str(Path(tmp.name) / "engine.db")
        store = Store(db)
        store.init()
        return store

    def make_config(self, **overrides):
        base = dict(
            database_path=":memory:",
            enabled=True,
            auto_bid=False,
            scout_interval_seconds=900,
            minimum_reward_cents=500,
            maximum_reward_cents=10_000,
            minimum_success_probability=Decimal("0.70"),
            minimum_expected_profit_cents=300,
            minimum_hourly_cents=1_500,
            compute_budget_cents=100,
            maximum_active_jobs=3,
            maximum_new_bids_per_day=10,
            allowed_currencies=("USD", "USDC", "USDT"),
            opentask_token="",
            opentask_base_url="https://opentask.ai/api",
        )
        base.update(overrides)
        return Config(**base)

    def make_bounty(self, **overrides):
        base = dict(
            source="opentask",
            external_id="task-1",
            title="Add regression tests for parser",
            description="Write pytest regression tests for a small parser bug.",
            reward_cents=2_000,
            currency="USDC",
            task_url="https://opentask.ai/tasks/task-1",
            execution_mode="pitch",
            match_score=95,
            updated_at="2026-09-18T00:00:00+00:00",
            raw={},
        )
        base.update(overrides)
        return Bounty(**base)

    def test_parse_budget(self):
        self.assertEqual(parse_budget("$12.50 USDC"), (1250, "USDC"))
        self.assertEqual(parse_budget("75 USD"), (7500, "USD"))
        self.assertIsNone(parse_budget("negotiable"))

    def test_high_fit_small_task_is_eligible(self):
        store = self.make_store()
        decision = decide(self.make_bounty(), store, self.make_config())
        self.assertTrue(decision.eligible)
        self.assertEqual(decision.category, "tests")
        self.assertGreaterEqual(decision.success_probability, Decimal("0.70"))
        self.assertGreaterEqual(decision.expected_profit_cents, 300)
        self.assertGreaterEqual(decision.expected_hourly_cents, 1500)

    def test_disallowed_task_is_rejected(self):
        store = self.make_store()
        bounty = self.make_bounty(
            title="Solve captcha workflow",
            description="Automate CAPTCHA solving for account creation.",
        )
        decision = decide(bounty, store, self.make_config())
        self.assertFalse(decision.eligible)
        self.assertEqual(decision.reason, "disallowed-task-type")

    def test_reward_caps_bound_autonomy(self):
        store = self.make_store()
        low = decide(
            self.make_bounty(reward_cents=200),
            store,
            self.make_config(),
        )
        high = decide(
            self.make_bounty(reward_cents=25_000),
            store,
            self.make_config(),
        )
        self.assertEqual(low.reason, "reward-below-minimum")
        self.assertEqual(high.reason, "reward-above-autonomy-cap")

    def test_unsupported_currency_is_rejected(self):
        store = self.make_store()
        decision = decide(
            self.make_bounty(currency="BTC"),
            store,
            self.make_config(),
        )
        self.assertFalse(decision.eligible)
        self.assertEqual(decision.reason, "unsupported-currency")

    def test_settlement_is_idempotent(self):
        store = self.make_store()
        bounty = self.make_bounty()
        decision = decide(bounty, store, self.make_config())
        store.upsert_job(bounty, decision)

        first = store.record_earning(
            source="opentask",
            external_id="task-1",
            settlement_ref="receipt-123",
            gross_cents=2000,
            fees_cents=90,
            currency="USDC",
        )
        second = store.record_earning(
            source="opentask",
            external_id="task-1",
            settlement_ref="receipt-123",
            gross_cents=2000,
            fees_cents=90,
            currency="USDC",
        )

        self.assertTrue(first)
        self.assertFalse(second)
        summary = store.summary()
        self.assertEqual(summary["earnings"][0]["gross_cents"], 2000)
        self.assertEqual(summary["earnings"][0]["fees_cents"], 90)
        self.assertEqual(summary["earnings"][0]["net_cents"], 1910)

    def test_opentask_normalization_prefers_structured_budget(self):
        rec = {
            "task": {
                "id": "abc",
                "title": "Document API",
                "budget": "$10 USDC",
                "createdAt": "2026-09-18T00:00:00Z",
            },
            "score": 88,
        }
        detail = {
            "task": {
                "id": "abc",
                "title": "Document API",
                "description": "Write API docs with examples.",
                "budgetAmount": 15,
                "budgetCurrency": "USDC",
                "executionMode": "pitch",
                "updatedAt": "2026-09-18T01:00:00Z",
            }
        }
        bounty = normalize_opentask(rec, detail)
        self.assertIsNotNone(bounty)
        assert bounty is not None
        self.assertEqual(bounty.reward_cents, 1500)
        self.assertEqual(bounty.currency, "USDC")
        self.assertEqual(bounty.match_score, 88)
        self.assertEqual(bounty.execution_mode, "pitch")

    def test_mark_accepts_decimal_decision_payload(self):
        store = self.make_store()
        bounty = self.make_bounty()
        decision = decide(bounty, store, self.make_config())
        store.upsert_job(bounty, decision)
        store.mark(
            bounty,
            "queued",
            "queue",
            {"decision": decision.__dict__},
        )
        self.assertEqual(store.summary()["statuses"]["queued"], 1)


if __name__ == "__main__":
    unittest.main()
