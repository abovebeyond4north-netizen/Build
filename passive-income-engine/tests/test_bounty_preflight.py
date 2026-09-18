import hashlib
import tempfile
import unittest
from pathlib import Path

from bounty_preflight import preflight_task
from bountyforge import Config


class FakePublicClient:
    def __init__(self, task):
        self.task = task
        self.reads = []

    def public_task_detail(self, task_id):
        self.reads.append(task_id)
        return {"task": dict(self.task)}


class BountyPreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.task = {
            "id": "buyer-csv-preflight",
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
            "updatedAt": "2026-09-18T09:00:00Z",
        }

    def config(self, *, token=""):
        return Config(
            database_path=str(self.root / ("with-token.db" if token else "no-token.db")),
            opentask_token=token,
            public_scout=True,
            auto_bid=True,
            auto_solve=True,
            auto_repo_verify=True,
            auto_deliver=True,
            reconcile_payments=True,
        )

    def test_no_auth_preflight_is_bid_ready_but_blocked_by_auth(self):
        client = FakePublicClient(self.task)
        result = preflight_task(
            self.task["id"],
            config=self.config(),
            client=client,
        )

        self.assertEqual(client.reads, [self.task["id"]])
        self.assertTrue(result["bid_ready"])
        self.assertEqual(result["blocked_by"], "marketplace_auth")
        self.assertFalse(result["marketplace_auth_present"])
        self.assertFalse(result["write_actions_performed"])
        self.assertEqual(
            result["fulfillment"],
            {"route": "solver", "kind": "csv_to_json_cli_package"},
        )
        self.assertTrue(result["artifact"]["verified"])
        self.assertEqual(result["artifact"]["filename"], "csv-to-json-converter.zip")
        self.assertFalse(result["artifact"]["artifact_written"])
        self.assertIn("dependency-free Python 3 CSV-to-JSON converter", result["bid_approach"])

    def test_preflight_can_write_only_static_safe_package(self):
        client = FakePublicClient(self.task)
        artifact_dir = self.root / "artifacts"
        result = preflight_task(
            self.task["id"],
            config=self.config(),
            client=client,
            artifact_dir=artifact_dir,
        )

        artifact = artifact_dir / "csv-to-json-converter.zip"
        self.assertTrue(artifact.is_file())
        self.assertTrue(result["artifact"]["artifact_written"])
        self.assertEqual(
            hashlib.sha256(artifact.read_bytes()).hexdigest(),
            result["artifact"]["sha256"],
        )

    def test_token_presence_still_does_not_turn_preflight_into_a_write(self):
        client = FakePublicClient(self.task)
        result = preflight_task(
            self.task["id"],
            config=self.config(token="scoped-test-token"),
            client=client,
        )

        self.assertTrue(result["bid_ready"])
        self.assertTrue(result["marketplace_auth_present"])
        self.assertEqual(result["blocked_by"], "explicit_bid_action")
        self.assertFalse(result["write_actions_performed"])
        self.assertEqual(client.reads, [self.task["id"]])

    def test_explicit_closed_status_blocks_preflight(self):
        task = dict(self.task)
        task["status"] = "closed"
        result = preflight_task(
            task["id"],
            config=self.config(),
            client=FakePublicClient(task),
        )
        self.assertFalse(result["bid_ready"])
        self.assertEqual(result["blocked_by"], "task_not_open")
        self.assertEqual(result["task_state"]["status"], "closed")
        self.assertIsNone(result["artifact"])

    def test_expired_deadline_blocks_preflight(self):
        task = dict(self.task)
        task["status"] = "open"
        task["deadlineAt"] = "2026-01-01T00:00:00Z"
        result = preflight_task(
            task["id"],
            config=self.config(),
            client=FakePublicClient(task),
        )
        self.assertFalse(result["bid_ready"])
        self.assertEqual(result["blocked_by"], "task_deadline_passed")
        self.assertEqual(result["task_state"]["deadline_field"], "deadlineAt")

    def test_explicit_can_bid_false_blocks_preflight(self):
        task = dict(self.task)
        task["status"] = "open"
        task["availableActions"] = {"canBid": False, "comment": True}
        result = preflight_task(
            task["id"],
            config=self.config(),
            client=FakePublicClient(task),
        )
        self.assertFalse(result["bid_ready"])
        self.assertEqual(result["blocked_by"], "task_not_biddable")
        self.assertTrue(result["task_state"]["explicit_bid_disabled"])

    def test_open_state_and_can_bid_true_remains_ready(self):
        task = dict(self.task)
        task["status"] = "open"
        task["availableActions"] = {"canBid": True, "comment": True}
        result = preflight_task(
            task["id"],
            config=self.config(),
            client=FakePublicClient(task),
        )
        self.assertTrue(result["bid_ready"])
        self.assertEqual(result["blocked_by"], "marketplace_auth")
        self.assertIn("canBid", result["task_state"]["available_actions"])
        self.assertIsInstance(result["task_state"]["updated_age_days"], int)

    def test_unsupported_task_is_not_bid_ready(self):
        task = {
            "id": "generic-task",
            "title": "Implement a small Python statistics utility",
            "description": "Create a Python utility that calculates descriptive statistics from a list.",
            "budgetAmount": 100,
            "budgetCurrency": "USDC",
            "executionMode": "pitch",
            "updatedAt": "2026-09-18T09:00:00Z",
        }
        result = preflight_task(
            task["id"],
            config=self.config(),
            client=FakePublicClient(task),
        )

        self.assertFalse(result["bid_ready"])
        self.assertIsNone(result["fulfillment"])
        self.assertIn(
            result["blocked_by"],
            {"success-probability-below-minimum", "no_autonomous_fulfillment_route"},
        )
        self.assertFalse(result["write_actions_performed"])


if __name__ == "__main__":
    unittest.main()
