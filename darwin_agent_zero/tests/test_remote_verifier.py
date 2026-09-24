import base64
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from dgm_zero.remote_verifier import (
    GitHubRemoteVerifier,
    REMOTE_RESULT_MARKER,
    RemoteEvaluationLedger,
    canonical_json,
    evaluation_key,
    parse_result_comment,
)


BASELINE = "def solve(x0):\n    return None\n"
FINALIST = (
    "def solve(x0):\n"
    "    return ' '.join(x0.lower().split())\n"
)


def make_request(nonce="1" * 64):
    return {
        "protocol_version": 2,
        "request_nonce": nonce,
        "capability": "normalize_text",
        "entrypoint": "solve",
        "baseline_source": BASELINE,
        "finalist_source": FINALIST,
        "required_score": 1.0,
        "minimum_gain": 0.05,
    }


def make_receipt(request, *, issue_number=41, workflow_sha="a" * 40):
    key = evaluation_key(request)
    return {
        "schema_version": 1,
        "remote_protocol_version": 2,
        "authority_protocol_version": 2,
        "authority_version": "1.1.0",
        "authority_digest": "2" * 64,
        "manifest_digest": "3" * 64,
        "evaluation_key": key,
        "request_digest": hashlib.sha256(canonical_json(request)).hexdigest(),
        "request_nonce": request["request_nonce"],
        "issue_number": issue_number,
        "capability": "normalize_text",
        "baseline_digest": hashlib.sha256(BASELINE.encode()).hexdigest(),
        "finalist_digest": hashlib.sha256(FINALIST.encode()).hexdigest(),
        "suite_digest": "4" * 64,
        "hidden_case_count": 32,
        "metamorphic_pair_count": 8,
        "containment_passed": True,
        "deterministic_replay": True,
        "baseline_score": 0.0,
        "finalist_score": 1.0,
        "baseline_metamorphic_score": 0.0,
        "finalist_metamorphic_score": 1.0,
        "delta": 1.0,
        "required_score": 1.0,
        "minimum_gain": 0.05,
        "passed": True,
        "reason": "passed",
        "context": {
            "repository": "abovebeyond4north-netizen/Build",
            "workflow": "Remote Verifier Authority",
            "workflow_ref": (
                "abovebeyond4north-netizen/Build/"
                ".github/workflows/remote_verifier_authority.yml@refs/heads/main"
            ),
            "workflow_sha": workflow_sha,
            "source_ref": "refs/heads/main",
            "run_id": "77",
            "run_attempt": "1",
            "event_name": "issues",
            "request_issue_author": "abovebeyond4north-netizen",
        },
        "created_at": 10.0,
        "containment_failure_count": 0,
    }


def result_comment(receipt):
    raw = (json.dumps(receipt, sort_keys=True, indent=2) + "\n").encode()
    digest = hashlib.sha256(raw).hexdigest()
    payload = base64.b64encode(raw).decode()
    return "\n".join(
        [
            REMOTE_RESULT_MARKER,
            "Remote verifier result: **PASS**",
            f"Receipt SHA-256: {digest}",
            f"Evaluation key: {receipt['evaluation_key']}",
            f"Request nonce: {receipt['request_nonce']}",
            "Workflow run: 77",
            "",
            "<details><summary>Attested receipt payload (base64)</summary>",
            "",
            payload,
            "",
            "</details>",
        ]
    )


class FakeRemoteVerifier(GitHubRemoteVerifier):
    def __init__(self, workspace, *, duplicate=False):
        self.created = 0
        self.attestation_commands = []
        self.duplicate = duplicate
        super().__init__(
            workspace,
            gh_bin="/usr/bin/false",
            token="test",
            poll_seconds=0.01,
            timeout_seconds=2.0,
        )

    def _run_gh(self, args):
        if args[:3] == ["api", "--method", "POST"]:
            self.created += 1
            return subprocess.CompletedProcess(args, 0, '{"number": 41}', "")
        if args and args[0] == "attestation":
            self.attestation_commands.append(tuple(args))
            return subprocess.CompletedProcess(
                args,
                0,
                '[{"verificationResult":{"verified":true}}]',
                "",
            )
        raise AssertionError(f"unexpected gh command: {args}")

    def _fetch_comments(self, issue_number):
        request = make_request()
        if self.duplicate and issue_number == 41:
            return [
                {
                    "user": {"login": "github-actions[bot]"},
                    "body": (
                        "<!-- dgm-remote-verifier-rejected:v2 -->\n"
                        "Remote verifier request rejected before hidden evaluation.\n"
                        "ValueError: hidden evidence already claimed by earlier issue 9"
                    ),
                }
            ]
        if self.duplicate and issue_number == 9:
            request["request_nonce"] = "9" * 64
            receipt = make_receipt(request, issue_number=9)
            return [
                {
                    "user": {"login": "github-actions[bot]"},
                    "body": result_comment(receipt),
                }
            ]
        receipt = make_receipt(request, issue_number=41)
        return [
            {
                "user": {"login": "github-actions[bot]"},
                "body": result_comment(receipt),
            }
        ]


class RemoteVerifierTests(unittest.TestCase):
    def test_evaluation_key_ignores_nonce(self):
        self.assertEqual(
            evaluation_key(make_request("1" * 64)),
            evaluation_key(make_request("2" * 64)),
        )

    def test_result_comment_detects_digest_tampering(self):
        receipt = make_receipt(make_request())
        parsed = parse_result_comment(result_comment(receipt))
        self.assertEqual(
            parsed["evaluation_key"],
            receipt["evaluation_key"],
        )

        tampered = result_comment(receipt).replace(
            "Receipt SHA-256: ",
            "Receipt SHA-256: " + ("0" * 64),
            1,
        )
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            parse_result_comment(tampered)

    def test_fresh_remote_result_is_attestation_verified_and_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            verifier = FakeRemoteVerifier(Path(tmp))
            decision = verifier.evaluate(
                capability="normalize_text",
                entrypoint="solve",
                baseline_source=BASELINE,
                finalist_source=FINALIST,
                required_score=1.0,
                minimum_gain=0.05,
            )
            self.assertTrue(decision.passed)
            self.assertTrue(decision.attestation_verified)
            self.assertFalse(decision.reused_remote_issue)
            self.assertEqual(verifier.created, 1)
            self.assertEqual(len(verifier.attestation_commands), 1)
            command = verifier.attestation_commands[0]
            self.assertIn("--signer-workflow", command)
            self.assertIn("--source-ref", command)
            self.assertIn("--deny-self-hosted-runners", command)
            self.assertEqual(len(RemoteEvaluationLedger(Path(tmp)).records()), 1)

    def test_duplicate_redirects_to_original_attested_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            verifier = FakeRemoteVerifier(Path(tmp), duplicate=True)
            decision = verifier.evaluate(
                capability="normalize_text",
                entrypoint="solve",
                baseline_source=BASELINE,
                finalist_source=FINALIST,
                required_score=1.0,
                minimum_gain=0.05,
            )
            self.assertTrue(decision.passed)
            self.assertTrue(decision.reused_remote_issue)
            self.assertEqual(decision.issue_number, 9)

    def test_local_ledger_prevents_second_remote_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            verifier = FakeRemoteVerifier(Path(tmp))
            first = verifier.evaluate(
                capability="normalize_text",
                entrypoint="solve",
                baseline_source=BASELINE,
                finalist_source=FINALIST,
                required_score=1.0,
                minimum_gain=0.05,
            )
            second = verifier.evaluate(
                capability="normalize_text",
                entrypoint="solve",
                baseline_source=BASELINE,
                finalist_source=FINALIST,
                required_score=1.0,
                minimum_gain=0.05,
            )
            self.assertEqual(first.record_hash, second.record_hash)
            self.assertEqual(verifier.created, 1)


if __name__ == "__main__":
    unittest.main()
