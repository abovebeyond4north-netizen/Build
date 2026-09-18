import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from bounty_bid_packet import (
    _canonical_bytes,
    build_bid_packet_from_preflight,
    prepare_bid_packet,
)
from bountyforge import Bounty, Config, OpenTaskClient, build_bid_request_body


class FakePublicClient:
    def __init__(self, task):
        self.task = dict(task)
        self.reads = []

    def public_task_detail(self, task_id):
        self.reads.append(task_id)
        return {"task": dict(self.task)}


class BidPacketTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.task = {
            "id": "buyer-csv-packet",
            "title": "Build a simple Python script to parse CSV files and generate JSON output",
            "description": (
                "Create a reusable Python script that can parse CSV files of any structure "
                "and convert them to properly formatted JSON output. The script should handle "
                "different delimiters, support custom output formatting options, and include "
                "error handling for invalid CSV files."
            ),
            "budgetAmount": 100,
            "budgetCurrency": "USDC",
            "executionMode": "pitch",
            "status": "open",
            "updatedAt": "2026-05-14T06:34:54.368Z",
        }
        self.config = Config(
            database_path=str(self.root / "engine.db"),
            opentask_token="",
            public_scout=True,
            reconcile_payments=False,
        )

    def test_packet_is_ready_without_performing_marketplace_write(self):
        client = FakePublicClient(self.task)
        packet = prepare_bid_packet(
            self.task["id"],
            config=self.config,
            client=client,
        )

        self.assertTrue(packet["packet_ready"])
        self.assertFalse(packet["write_actions_performed"])
        self.assertFalse(packet["intent"]["guards"]["write_action_enabled"])
        self.assertEqual(packet["current_preflight_blocker"], "marketplace_auth")
        self.assertFalse(packet["marketplace_auth_present"])
        self.assertEqual(client.reads, [self.task["id"]])

        request = packet["intent"]["request"]
        self.assertEqual(request["method"], "POST")
        self.assertEqual(
            request["path"],
            f"/api/agent/tasks/{self.task['id']}/bids",
        )
        self.assertEqual(
            request["body"]["expectedTaskUpdatedAt"],
            self.task["updatedAt"],
        )
        self.assertEqual(request["body"]["priceAmount"], 100.0)
        self.assertEqual(request["body"]["priceCurrency"], "USDC")
        self.assertEqual(request["body"]["etaDays"], 1)
        self.assertIn(
            "dependency-free Python 3 CSV-to-JSON converter",
            request["body"]["approach"],
        )

        fulfillment = packet["intent"]["fulfillment"]
        self.assertEqual(fulfillment["kind"], "csv_to_json_cli_package")
        self.assertRegex(fulfillment["artifact_sha256"], r"^[0-9a-f]{64}$")
        self.assertGreater(fulfillment["artifact_size_bytes"], 0)

    def test_intent_hash_is_stable_for_unchanged_task_terms(self):
        first = prepare_bid_packet(
            self.task["id"],
            config=self.config,
            client=FakePublicClient(self.task),
        )
        second = prepare_bid_packet(
            self.task["id"],
            config=self.config,
            client=FakePublicClient(self.task),
        )
        self.assertEqual(first["intent"], second["intent"])
        self.assertEqual(first["intent_sha256"], second["intent_sha256"])
        self.assertEqual(
            first["intent_sha256"],
            hashlib.sha256(_canonical_bytes(first["intent"])).hexdigest(),
        )

    def test_packet_request_matches_production_create_bid_payload(self):
        packet = prepare_bid_packet(
            self.task["id"],
            config=self.config,
            client=FakePublicClient(self.task),
        )
        request_body = packet["intent"]["request"]["body"]

        bounty = Bounty(
            source="opentask",
            external_id=self.task["id"],
            title=self.task["title"],
            description=self.task["description"],
            reward_cents=10000,
            currency="USDC",
            task_url=f"https://opentask.ai/tasks/{self.task['id']}",
            execution_mode="pitch",
            match_score=98,
            updated_at=self.task["updatedAt"],
            raw={},
        )
        expected = build_bid_request_body(
            bounty,
            eta_days=1,
            approach=request_body["approach"],
        )
        self.assertEqual(request_body, expected)

        client = OpenTaskClient(
            Config(
                database_path=str(self.root / "production-client.db"),
                opentask_token="test-token",
            )
        )
        captured = {}

        def fake_request(method, path, payload=None, headers=None):
            captured.update(
                method=method,
                path=path,
                payload=payload,
                headers=headers,
            )
            return {"bid": {"id": "dry-test"}}

        client._request = fake_request
        client.create_bid(
            bounty,
            eta_days=1,
            approach=request_body["approach"],
        )
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(
            captured["path"],
            f"/agent/tasks/{self.task['id']}/bids",
        )
        self.assertEqual(captured["payload"], request_body)

    def test_unsupported_preflight_cannot_produce_ready_packet(self):
        task = {
            "id": "unsupported-packet",
            "title": "Implement a small Python statistics utility",
            "description": "Create descriptive statistics from arbitrary input.",
            "budgetAmount": 100,
            "budgetCurrency": "USDC",
            "executionMode": "pitch",
            "status": "open",
            "updatedAt": "2026-09-18T10:00:00Z",
        }
        packet = prepare_bid_packet(
            task["id"],
            config=self.config,
            client=FakePublicClient(task),
        )
        self.assertFalse(packet["packet_ready"])
        self.assertFalse(packet["write_actions_performed"])

    def test_blocked_preflight_packet_has_no_request_body(self):
        packet = build_bid_packet_from_preflight(
            {
                "task_id": "closed-task",
                "bid_ready": False,
                "blocked_by": "task_not_open",
            }
        )
        self.assertFalse(packet["packet_ready"])
        self.assertEqual(packet["blocked_by"], "task_not_open")
        self.assertNotIn("intent", packet)
        self.assertFalse(packet["write_actions_performed"])


if __name__ == "__main__":
    unittest.main()
