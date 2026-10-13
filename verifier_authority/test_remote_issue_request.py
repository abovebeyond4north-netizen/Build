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


def request(finalist=NORMALIZER, nonce=NONCE):
    return {
        "protocol_version": 2,
        "request_nonce": nonce,
        "capability": "normalize_text",
        "entrypoint": "solve",
        "baseline_source": BASELINE,
        "finalist_source": finalist,
        "required_score": 1.0,
        "minimum_gain": 0.05,
    }


def event(body=None, title=None, number=321):
    payload = body if body is not None else request()
    expected = remote_issue_request.expected_issue_title(payload)
    return {
        "action": "opened",
        "issue": {
            "number": number,
            "title": expected if title is None else title,
            "body": json.dumps(payload),
            "user": {"login": "abovebeyond4north-netizen"},
        },
    }


class RemoteIssueRequestTests(unittest.TestCase):
    def test_preflight_binds_exact_deterministic_title(self):
        item = event()
        preflight = remote_issue_request.build_preflight(item)
        self.assertEqual(
            preflight["expected_title"],
            remote_issue_request.TITLE_PREFIX + preflight["evaluation_key"],
        )
        self.assertEqual(preflight["issue_number"], 321)

        bad = event(title="[DGM-VERIFY] wrong")
        with self.assertRaisesRegex(ValueError, "deterministic evaluation key"):
            remote_issue_request.build_preflight(bad)

    def test_evaluation_key_ignores_nonce_but_binds_candidate(self):
        first = request(nonce="1" * 64)
        second = request(nonce="2" * 64)
        self.assertEqual(
            remote_issue_request.evaluation_key(first),
            remote_issue_request.evaluation_key(second),
        )

        changed = request(
            finalist="def solve(x0):\n    return x0\n",
            nonce="2" * 64,
        )
        self.assertNotEqual(
            remote_issue_request.evaluation_key(first),
            remote_issue_request.evaluation_key(changed),
        )

    def test_only_earliest_matching_issue_can_claim_hidden_evidence(self):
        item = event(number=12)
        preflight = remote_issue_request.build_preflight(item)
        pages = [
            [
                {"number": 12, "title": preflight["expected_title"]},
                {"number": 15, "title": preflight["expected_title"]},
                {"number": 9, "title": "unrelated"},
            ]
        ]
        claim = remote_issue_request.verify_first_issue_claim(
            preflight,
            pages,
        )
        self.assertTrue(claim["claimed"])
        self.assertEqual(claim["first_issue_number"], 12)

        later = dict(preflight)
        later["issue_number"] = 15
        with self.assertRaisesRegex(ValueError, "earlier issue 12"):
            remote_issue_request.verify_first_issue_claim(
                later,
                pages,
            )

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
            number, _, parsed = remote_issue_request.require_issue_event(item)
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
        self.assertEqual(
            receipt["evaluation_key"],
            remote_issue_request.evaluation_key(parsed),
        )
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
        number, _, parsed = remote_issue_request.require_issue_event(item)
        receipt = remote_issue_request.evaluate_remote(
            issue_number=number,
            request=parsed,
            context={},
        )
        self.assertFalse(receipt["passed"])
        self.assertLess(receipt["finalist_score"], 1.0)

    def test_nonce_is_strictly_validated(self):
        bad = request(nonce="abc")
        item = {
            "action": "opened",
            "issue": {
                "number": 321,
                "title": "[DGM-VERIFY] malformed",
                "body": json.dumps(bad),
                "user": {"login": "abovebeyond4north-netizen"},
            },
        }
        with self.assertRaisesRegex(ValueError, "request_nonce"):
            remote_issue_request.build_preflight(item)

    def test_request_digest_changes_with_nonce(self):
        first = request(nonce="1" * 64)
        second = request(nonce="2" * 64)
        receipt_a = remote_issue_request.evaluate_remote(
            issue_number=321,
            request=first,
            context={},
        )
        receipt_b = remote_issue_request.evaluate_remote(
            issue_number=321,
            request=second,
            context={},
        )
        self.assertNotEqual(
            receipt_a["request_digest"],
            receipt_b["request_digest"],
        )
        self.assertEqual(
            receipt_a["evaluation_key"],
            receipt_b["evaluation_key"],
        )

    def test_public_comment_contains_exact_receipt_bytes(self):
        item = event()
        number, _, parsed = remote_issue_request.require_issue_event(item)
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
                "<!-- dgm-remote-verifier-result:v2 -->",
                body,
            )
            self.assertIn(NONCE, body)
            self.assertIn(receipt["evaluation_key"], body)
            digest = remote_issue_request.sha256_bytes(
                receipt_path.read_bytes()
            )
            self.assertIn(digest, body)


if __name__ == "__main__":
    unittest.main()
