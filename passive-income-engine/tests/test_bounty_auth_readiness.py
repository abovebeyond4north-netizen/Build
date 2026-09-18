import json
import tempfile
import unittest
from pathlib import Path

from bountyforge import Config, authenticated_bid_readiness


class FakeAuthClient:
    def __init__(self, *, checkpoint="marketplace_action_required", fail=None):
        self.checkpoint = checkpoint
        self.fail = fail
        self.calls = []

    def get_me(self):
        self.calls.append("get_me")
        if self.fail == "me":
            raise RuntimeError("profile failed")
        return {
            "profile": {
                "id": "profile-test",
                "handle": "tester",
                "displayName": "Test Agent",
            }
        }

    def get_onboarding_status(self):
        self.calls.append("onboarding")
        if self.fail == "onboarding":
            raise RuntimeError("onboarding failed")
        return {
            "complete": self.checkpoint == "activated",
            "progress": {
                "completedRequiredSteps": 5,
                "requiredSteps": 6,
                "percentage": 83,
            },
            "checkpoint": {
                "code": self.checkpoint,
                "status": "complete" if self.checkpoint == "activated" else "action_required",
            },
        }

    def list_tasks(self, *, status="open", limit=1):
        self.calls.append(("list_tasks", status, limit))
        if self.fail == "tasks":
            raise RuntimeError("tasks failed")
        return []

    def list_own_bids(self, *, task_id=None, status=None, limit=20):
        self.calls.append(("list_own_bids", task_id, status, limit))
        if self.fail == "bids":
            raise RuntimeError("bids failed")
        return []


class AuthReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def config(self, *, scopes=(), token="super-secret-token"):
        return Config(
            database_path=str(Path(self.tmp.name) / "engine.db"),
            opentask_token=token,
            opentask_declared_scopes=tuple(scopes),
            public_scout=False,
            reconcile_payments=False,
        )

    def test_missing_token_fails_closed_without_network_calls(self):
        client = FakeAuthClient()
        result = authenticated_bid_readiness(
            self.config(
                token="",
                scopes=("profile:read", "tasks:read", "bids:read", "bids:write"),
            ),
            client,
        )
        self.assertFalse(result["ready_for_bid"])
        self.assertEqual(result["blocked_by"], "marketplace_auth")
        self.assertEqual(client.calls, [])

    def test_missing_declared_write_scope_fails_closed_before_reads(self):
        client = FakeAuthClient()
        result = authenticated_bid_readiness(
            self.config(scopes=("profile:read", "tasks:read")),
            client,
        )
        self.assertFalse(result["ready_for_bid"])
        self.assertEqual(result["blocked_by"], "declared_scopes_missing")
        self.assertEqual(result["missing_declared_scopes"], ["bids:read", "bids:write"])
        self.assertEqual(client.calls, [])

    def test_readiness_verifies_identity_onboarding_and_task_read(self):
        client = FakeAuthClient()
        result = authenticated_bid_readiness(
            self.config(scopes=("bids:write", "profile:read", "tasks:read")),
            client,
        )
        self.assertTrue(result["ready_for_bid"])
        self.assertIsNone(result["blocked_by"])
        self.assertTrue(result["profile_read_verified"])
        self.assertTrue(result["onboarding_read_verified"])
        self.assertTrue(result["tasks_read_verified"])
        self.assertEqual(result["profile"]["id"], "profile-test")
        self.assertEqual(result["checkpoint"]["code"], "marketplace_action_required")
        self.assertIn("operator-declared", result["warnings"][0])
        self.assertEqual(
            client.calls,
            [
            "get_me",
            "onboarding",
            ("list_tasks", "open", 1),
            ("list_own_bids", None, None, 1),
        ],
        )

        serialized = json.dumps(result, sort_keys=True)
        self.assertNotIn("super-secret-token", serialized)
        self.assertNotIn("Authorization", serialized)

    def test_pre_marketplace_onboarding_state_blocks_bid(self):
        client = FakeAuthClient(checkpoint="capability_required")
        result = authenticated_bid_readiness(
            self.config(scopes=("bids:write", "profile:read", "tasks:read")),
            client,
        )
        self.assertFalse(result["ready_for_bid"])
        self.assertEqual(result["blocked_by"], "onboarding_incomplete")

    def test_activated_onboarding_is_allowed(self):
        client = FakeAuthClient(checkpoint="activated")
        result = authenticated_bid_readiness(
            self.config(scopes=("bids:write", "profile:read", "tasks:read")),
            client,
        )
        self.assertTrue(result["ready_for_bid"])
        self.assertTrue(result["checkpoint"]["complete"])

    def test_read_failures_fail_closed_and_are_bounded(self):
        for failure, blocker in (
            ("me", "profile_read_failed"),
            ("onboarding", "onboarding_read_failed"),
            ("tasks", "tasks_read_failed"),
            ("bids", "bids_read_failed"),
        ):
            with self.subTest(failure=failure):
                client = FakeAuthClient(fail=failure)
                result = authenticated_bid_readiness(
                    self.config(scopes=("bids:write", "profile:read", "tasks:read")),
                    client,
                )
                self.assertFalse(result["ready_for_bid"])
                self.assertEqual(result["blocked_by"], blocker)
                self.assertLessEqual(len(result.get("error", "")), 500)


if __name__ == "__main__":
    unittest.main()
