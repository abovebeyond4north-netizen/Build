import base64
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import authority


BASELINE = "def solve(x0):\n    return None\n"
NORMALIZER = (
    "def solve(x0):\n"
    "    return ' '.join(x0.lower().split())\n"
)


def verify_signature(public_key_pem, payload, signature_b64):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        public_key = root / "public.pem"
        signature = root / "signature.bin"
        public_key.write_text(
            public_key_pem,
            encoding="utf-8",
        )
        signature.write_bytes(
            base64.b64decode(signature_b64)
        )
        completed = subprocess.run(
            [
                authority.openssl_bin(),
                "dgst",
                "-sha256",
                "-verify",
                str(public_key),
                "-signature",
                str(signature),
            ],
            input=authority.canonical_json(payload),
            capture_output=True,
            check=False,
        )
        return completed.returncode == 0


class VerifierAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.state = self.root / "state"
        self.env = patch.dict(
            os.environ,
            {
                "DGM_VERIFIER_AUTHORITY_STATE": str(
                    self.state
                )
            },
            clear=False,
        )
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def request(self, **updates):
        request = {
            "protocol_version": authority.PROTOCOL_VERSION,
            "capability": "normalize_text",
            "entrypoint": "solve",
            "baseline_source": BASELINE,
            "finalist_source": NORMALIZER,
            "required_score": 1.0,
            "minimum_gain": 0.05,
        }
        request.update(updates)
        return request

    def test_identity_manifest_is_signed(self):
        response = authority.authority_identity()
        identity = response["identity"]
        self.assertEqual(
            identity["authority_version"],
            authority.AUTHORITY_VERSION,
        )
        self.assertEqual(
            identity["protocol_version"],
            authority.PROTOCOL_VERSION,
        )
        self.assertTrue(
            verify_signature(
                response["public_key_pem"],
                identity,
                response["identity_signature"],
            )
        )
        self.assertTrue(
            (self.state / "authority-private.pem").is_file()
        )
        mode = (
            self.state
            / "authority-private.pem"
        ).stat().st_mode & 0o777
        self.assertEqual(mode & 0o077, 0)

    def test_evaluation_keeps_seed_private_and_signs_receipt(self):
        response = authority.evaluate_request(
            self.request()
        )
        receipt = response["receipt"]
        self.assertTrue(receipt["passed"])
        self.assertTrue(
            receipt["containment_passed"]
        )
        self.assertEqual(
            receipt["finalist_score"],
            1.0,
        )
        self.assertEqual(
            receipt["finalist_metamorphic_score"],
            1.0,
        )
        self.assertNotIn("seed", receipt)
        self.assertTrue(
            verify_signature(
                response["public_key_pem"],
                receipt,
                response["signature"],
            )
        )

        private = json.loads(
            authority.ledger_path()
            .read_text(encoding="utf-8")
            .strip()
        )
        self.assertIsInstance(private["seed"], int)
        self.assertNotIn("seed", private["receipt"])

    def test_same_candidate_is_one_shot(self):
        first = authority.evaluate_request(
            self.request()
        )
        second = authority.evaluate_request(
            self.request()
        )
        self.assertFalse(first["reused"])
        self.assertTrue(second["reused"])
        self.assertEqual(
            first["receipt"]["evaluation_id"],
            second["receipt"]["evaluation_id"],
        )
        self.assertEqual(
            first["signature"],
            second["signature"],
        )
        self.assertEqual(
            len(
                authority.ledger_path()
                .read_text(encoding="utf-8")
                .splitlines()
            ),
            1,
        )

    def test_threshold_change_does_not_redraw_suite(self):
        authority.evaluate_request(self.request())
        with self.assertRaisesRegex(
            ValueError,
            "different acceptance thresholds",
        ):
            authority.evaluate_request(
                self.request(required_score=0.9)
            )
        self.assertEqual(
            len(
                authority.ledger_path()
                .read_text(encoding="utf-8")
                .splitlines()
            ),
            1,
        )

    def test_replay_reproduces_signed_evidence(self):
        result = authority.evaluate_request(
            self.request()
        )
        receipt = result["receipt"]
        replay_result = authority.replay_request(
            {
                "protocol_version": (
                    authority.PROTOCOL_VERSION
                ),
                "evaluation_id": (
                    receipt["evaluation_id"]
                ),
                "baseline_source": BASELINE,
                "finalist_source": NORMALIZER,
            }
        )
        replay = replay_result["replay"]
        self.assertTrue(replay["matches_original"])
        self.assertEqual(
            replay["suite_digest"],
            receipt["suite_digest"],
        )
        self.assertEqual(
            replay["finalist_score"],
            receipt["finalist_score"],
        )
        self.assertTrue(
            verify_signature(
                replay_result["public_key_pem"],
                replay,
                replay_result["replay_signature"],
            )
        )

    def test_visible_style_overfit_fails_hidden_and_metamorphic_evidence(self):
        overfit = (
            "def solve(x0):\n"
            "    if x0 == '  Hello   WORLD  ':\n"
            "        return 'hello world'\n"
            "    if x0 == 'A  B':\n"
            "        return 'a b'\n"
            "    return x0\n"
        )
        result = authority.evaluate_request(
            self.request(finalist_source=overfit)
        )
        self.assertFalse(result["receipt"]["passed"])
        self.assertLess(
            result["receipt"]["finalist_score"],
            1.0,
        )

    def test_containment_probe_passes(self):
        passed, failures = (
            authority.containment_self_test()
        )
        self.assertTrue(passed, failures)


if __name__ == "__main__":
    unittest.main()
