import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import remote_issue_request


BASELINE = "def solve(x0):\n    return None\n"
NORMALIZER = (
    "def solve(x0):\n"
    "    return ' '.join(x0.lower().split())\n"
)
NONCE = "a" * 64


def request(finalist=NORMALIZER):
    return {
        "protocol_version": 2,
        "request_nonce": NONCE,
        "capability": "normalize_text",
        "entrypoint": "solve",
        "baseline_source": BASELINE,
        "finalist_source": finalist,
        "required_score": 1.0,
        "minimum_gain": 0.05,
    }


def event(body=None, title="[DGM-VERIFY] normalize_text"):
    return {
        "action": "opened",
        "issue": {
            "number": 321,
            "title": title,
            "body": json.dumps(body if body is not None else request()),
            "user": {"login": "abovebeyond4north-netizen"},
        },
    }


class RemoteIssueRequestTests(unittest.TestCase):
    def test_valid_remote_request_passes_without_exposing_seed(self):
        with patch.dict(
            os.environ,
            {
                "GITHUB_REPOSITORY": "abovebeyond4north-netizen/Build",
                "GITHUB_WORKFLOW": "Remote Verifier Authority",
                "GITHUB_WORKFLOW_REF": (
                    "abovebeyond4north-netizen/Build/"
                    ".github/workflows/remote_verifier_authority.yml@refs/heads/main"
                ),
                "GITHUB_SHA": "b" * 40,
                "GITHUB_REF": "refs/heads/main",
                "GITHUB_RUN_ID": "123456",
                "GITHUB_RUN_ATTEMPT": "1",
                "GITHUB_EVENT_NAME": "issues",
            },
            clear=False,
        ):
            item = event()
            number, parsed = remote_issue_request.require_issue_event(item)
            receipt = remote_issue_request.evaluate_remote(
                issue_number=number,
                request=parsed,
                context=remote_issue_request.request_context(item),
            )

        self.assertTrue(receipt["passed"])
        self.assertTrue(receipt["containment_passed"])
        self.assertTrue(receipt["deterministic_replay"])
        self.assertEqual(receipt["finalist_score"], 1.0)
        self.assertEqual(receipt["finalist_metamorphic_score"], 1.0)
        self.assertEqual(receipt["request_nonce"], NONCE)
        self.assertEqual(receipt["issue_number"], 321)
        serialized = json.dumps(receipt, sort_keys=True)
        self.assertNotIn('"seed"', serialized)
        self.assertNotIn("hidden_normalize_", serialized)

    def test_overfit_candidate_fails_remote_hidden_suite(self):
        overfit = (
            "def solve(x0):\n"
            "    if x0 == '  Hello   WORLD  ':\n"
            "        return 'hello world'\n"
            "    return x0\n"
        )
        item = event(request(overfit))
        number, parsed = remote_issue_request.require_issue_event(item)
        receipt = remote_issue_request.evaluate_remote(
            issue_number=number,
            request=parsed,
            context={},
        )
        self.assertFalse(receipt["passed"])
        self.assertLess(receipt["finalist_score"], 1.0)

    def test_issue_title_and_nonce_are_strictly_bound(self):
        with self.assertRaisesRegex(ValueError, "title"):
            remote_issue_request.require_issue_event(
                event(title="normal issue")
            )

        bad = request()
        bad["request_nonce"] = "abc"
        number, parsed = remote_issue_request.require_issue_event(event(bad))
        self.assertEqual(number, 321)
        with self.assertRaisesRegex(ValueError, "request_nonce"):
            remote_issue_request.evaluate_remote(
                issue_number=number,
                request=parsed,
                context={},
            )

    def test_request_digest_changes_with_candidate(self):
        item_a = event()
        _, parsed_a = remote_issue_request.require_issue_event(item_a)
        receipt_a = remote_issue_request.evaluate_remote(
            issue_number=321,
            request=parsed_a,
            context={},
        )

        changed = request("def solve(x0):\n    return x0\n")
        item_b = event(changed)
        _, parsed_b = remote_issue_request.require_issue_event(item_b)
        receipt_b = remote_issue_request.evaluate_remote(
            issue_number=321,
            request=parsed_b,
            context={},
        )

        self.assertNotEqual(
            receipt_a["request_digest"],
            receipt_b["request_digest"],
        )

    def test_public_comment_contains_exact_receipt_bytes(self):
        item = event()
        number, parsed = remote_issue_request.require_issue_event(item)
        receipt = remote_issue_request.evaluate_remote(
            issue_number=number,
            request=parsed,
            context={"run_id": "77"},
        )
        with tempfile.TemporaryDirectory() as tmp:
            receipt_path, comment_path = remote_issue_request.write_outputs(
                receipt,
                Path(tmp),
            )
            payload = json.loads(
                comment_path.read_text(encoding="utf-8")
            )
            body = payload["body"]
            self.assertIn(
                "<!-- dgm-remote-verifier-result:v1 -->",
                body,
            )
            self.assertIn(NONCE, body)
            digest = remote_issue_request.sha256_bytes(
                receipt_path.read_bytes()
            )
            self.assertIn(digest, body)


if __name__ == "__main__":
    unittest.main()
