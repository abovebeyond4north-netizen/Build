import tempfile
import unittest
from pathlib import Path

from bounty_bid_packet import prepare_bid_packet
from bounty_submit_bid import CONFIRM_PHRASE, submit_manual_bid
from bountyforge import Config


class FakeBidClient:
    def __init__(self, task, *, existing=None, create_mode="success"):
        self.task = dict(task)
        self.existing = list(existing or [])
        self.create_mode = create_mode
        self.calls = []
        self.create_calls = 0
        self.created_bid = None

    def get_me(self):
        self.calls.append(("get_me",))
        return {"profile": {"id": "profile-test", "handle": "tester"}}

    def get_onboarding_status(self):
        self.calls.append(("onboarding",))
        return {
            "complete": False,
            "progress": {"percentage": 90},
            "checkpoint": {
                "code": "marketplace_action_required",
                "status": "action_required",
            },
        }

    def list_tasks(self, *, status="open", limit=1):
        self.calls.append(("list_tasks", status, limit))
        return []

    def public_task_detail(self, task_id):
        self.calls.append(("public_task_detail", task_id))
        return {"task": dict(self.task)}

    def list_own_bids(self, *, task_id=None, status=None, limit=20):
        self.calls.append(("list_own_bids", task_id, status, limit))
        if task_id is None:
            return []
        if self.created_bid is not None:
            return [dict(self.created_bid)]
        return [dict(item) for item in self.existing]

    def create_bid(self, bounty, *, eta_days, approach):
        self.calls.append(("create_bid", bounty.external_id, eta_days, approach))
        self.create_calls += 1
        bid = {
            "id": "bid-created-1",
            "status": "active",
            "taskId": bounty.external_id,
            "createdAt": "2026-09-18T10:40:00Z",
        }
        if self.create_mode == "success":
            self.created_bid = bid
            return {"bid": dict(bid)}
        if self.create_mode == "fail_after_commit":
            self.created_bid = bid
            raise RuntimeError("simulated connection reset after commit")
        if self.create_mode == "fail_before_commit":
            raise RuntimeError("simulated connection failure before commit")
        raise AssertionError("unexpected create mode")


class ManualBidTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.task = {
            "id": "buyer-csv-manual",
            "title": "Build a simple Python script to parse CSV files and generate JSON output",
            "description": (
                "Create a reusable Python script that can parse CSV files of any structure "
                "and convert them to properly formatted JSON output. Handle delimiters, "
                "custom output formatting, and invalid CSV errors."
            ),
            "budgetAmount": 100,
            "budgetCurrency": "USDC",
            "executionMode": "pitch",
            "status": "open",
            "updatedAt": "2026-05-14T06:34:54.368Z",
        }

    def config(self, *, token="test-token"):
        return Config(
            database_path=str(self.root / "engine.db"),
            opentask_token=token,
            opentask_declared_scopes=(
                "bids:read",
                "bids:write",
                "profile:read",
                "tasks:read",
            ),
            public_scout=False,
            reconcile_payments=False,
            auto_bid=False,
        )

    def intent_hash(self, client):
        packet = prepare_bid_packet(
            self.task["id"],
            config=self.config(),
            client=client,
        )
        self.assertTrue(packet["packet_ready"])
        return packet["intent_sha256"]

    def test_wrong_confirmation_blocks_before_any_network_call(self):
        client = FakeBidClient(self.task)
        result = submit_manual_bid(
            self.task["id"],
            expected_intent_sha256="a" * 64,
            confirm_phrase="NO",
            config=self.config(),
            client=client,
        )
        self.assertEqual(result["blocked_by"], "confirmation_required")
        self.assertFalse(result["write_attempted"])
        self.assertEqual(client.calls, [])

    def test_missing_auth_blocks_without_create_bid(self):
        client = FakeBidClient(self.task)
        result = submit_manual_bid(
            self.task["id"],
            expected_intent_sha256="a" * 64,
            confirm_phrase=CONFIRM_PHRASE,
            config=self.config(token=""),
            client=client,
        )
        self.assertEqual(result["blocked_by"], "marketplace_auth")
        self.assertFalse(result["write_attempted"])
        self.assertEqual(client.create_calls, 0)

    def test_existing_bid_blocks_second_write(self):
        client = FakeBidClient(
            self.task,
            existing=[
                {
                    "id": "bid-existing",
                    "status": "active",
                    "taskId": self.task["id"],
                }
            ],
        )
        result = submit_manual_bid(
            self.task["id"],
            expected_intent_sha256="a" * 64,
            confirm_phrase=CONFIRM_PHRASE,
            config=self.config(),
            client=client,
        )
        self.assertEqual(result["blocked_by"], "existing_bid")
        self.assertFalse(result["write_attempted"])
        self.assertEqual(result["existing_bids"][0]["id"], "bid-existing")
        self.assertEqual(client.create_calls, 0)

    def test_intent_hash_mismatch_blocks_write(self):
        client = FakeBidClient(self.task)
        good_hash = self.intent_hash(client)
        bad_hash = ("0" if good_hash[0] != "0" else "1") + good_hash[1:]
        result = submit_manual_bid(
            self.task["id"],
            expected_intent_sha256=bad_hash,
            confirm_phrase=CONFIRM_PHRASE,
            config=self.config(),
            client=client,
        )
        self.assertEqual(result["blocked_by"], "intent_hash_mismatch")
        self.assertFalse(result["write_attempted"])
        self.assertEqual(client.create_calls, 0)

    def test_exact_fresh_packet_submits_once(self):
        client = FakeBidClient(self.task)
        intent_hash = self.intent_hash(client)
        result = submit_manual_bid(
            self.task["id"],
            expected_intent_sha256=intent_hash,
            confirm_phrase=CONFIRM_PHRASE,
            config=self.config(),
            client=client,
        )
        self.assertTrue(result["write_attempted"])
        self.assertTrue(result["write_confirmed"])
        self.assertFalse(result["write_outcome_unknown"])
        self.assertIsNone(result["blocked_by"])
        self.assertEqual(result["bid"]["id"], "bid-created-1")
        self.assertEqual(client.create_calls, 1)

    def test_failure_after_commit_is_recovered_by_bid_readback(self):
        client = FakeBidClient(self.task, create_mode="fail_after_commit")
        intent_hash = self.intent_hash(client)
        result = submit_manual_bid(
            self.task["id"],
            expected_intent_sha256=intent_hash,
            confirm_phrase=CONFIRM_PHRASE,
            config=self.config(),
            client=client,
        )
        self.assertTrue(result["write_attempted"])
        self.assertTrue(result["write_confirmed"])
        self.assertTrue(result["reconciled_after_error"])
        self.assertFalse(result["write_outcome_unknown"])
        self.assertEqual(result["bid"]["id"], "bid-created-1")
        self.assertEqual(client.create_calls, 1)

    def test_unreconciled_write_failure_never_retries(self):
        client = FakeBidClient(self.task, create_mode="fail_before_commit")
        intent_hash = self.intent_hash(client)
        result = submit_manual_bid(
            self.task["id"],
            expected_intent_sha256=intent_hash,
            confirm_phrase=CONFIRM_PHRASE,
            config=self.config(),
            client=client,
        )
        self.assertTrue(result["write_attempted"])
        self.assertFalse(result["write_confirmed"])
        self.assertTrue(result["write_outcome_unknown"])
        self.assertEqual(result["blocked_by"], "bid_write_outcome_unknown")
        self.assertEqual(client.create_calls, 1)


if __name__ == "__main__":
    unittest.main()
