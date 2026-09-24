import json
import tempfile
import unittest
from pathlib import Path

from dgm_zero.protected_evaluator import (
    ProtectedEvaluationLedger,
    ProtectedEvaluator,
)
from dgm_zero.protected_evaluator_worker import (
    build_hidden_cases,
    containment_self_test,
)


BASELINE = "def solve(x0):\n    return None\n"
NORMALIZER = (
    "def solve(x0):\n"
    "    return ' '.join(x0.lower().split())\n"
)


class LegacyWorkerRegressionTests(unittest.TestCase):
    def test_old_worker_remains_deterministic_but_is_not_authority(self):
        first = build_hidden_cases("normalize_text", 12345)
        repeat = build_hidden_cases("normalize_text", 12345)
        second = build_hidden_cases("normalize_text", 54321)
        self.assertEqual(first, repeat)
        self.assertNotEqual(first, second)
        self.assertEqual(len(first), 32)

    def test_legacy_containment_regression_still_passes(self):
        passed, failures = containment_self_test()
        self.assertTrue(passed, failures)


class ProtectedEvaluatorTests(unittest.TestCase):
    @staticmethod
    def evaluator(root: Path) -> ProtectedEvaluator:
        return ProtectedEvaluator(
            root / "workspace",
            authority_state=root / "authority-state",
            authority_mode="process",
        )

    def test_signed_external_evaluation_passes_and_is_replayed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evaluator = self.evaluator(root)
            decision = evaluator.evaluate(
                capability="normalize_text",
                entrypoint="solve",
                baseline_source=BASELINE,
                finalist_source=NORMALIZER,
                required_score=1.0,
                minimum_gain=0.05,
            )

            self.assertIsNotNone(decision)
            self.assertTrue(decision.passed)
            self.assertTrue(decision.containment_passed)
            self.assertEqual(decision.finalist_score, 1.0)
            self.assertEqual(decision.finalist_metamorphic_score, 1.0)
            self.assertGreaterEqual(decision.delta, 0.05)
            self.assertEqual(decision.case_count, 32)
            self.assertEqual(decision.metamorphic_pair_count, 8)
            self.assertIsNone(decision.seed)
            self.assertTrue(decision.authority_signature)
            self.assertTrue(decision.replay_signature)
            self.assertTrue(decision.replay_verified)
            self.assertTrue(decision.record_hash)
            self.assertTrue(
                (
                    root
                    / "workspace"
                    / "verifier_authority_trust.json"
                ).is_file()
            )

    def test_same_finalist_reuses_same_authority_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evaluator = self.evaluator(root)
            first = evaluator.evaluate(
                capability="normalize_text",
                entrypoint="solve",
                baseline_source=BASELINE,
                finalist_source=NORMALIZER,
                required_score=1.0,
                minimum_gain=0.05,
            )
            second = evaluator.evaluate(
                capability="normalize_text",
                entrypoint="solve",
                baseline_source=BASELINE,
                finalist_source=NORMALIZER,
                required_score=1.0,
                minimum_gain=0.05,
            )

            self.assertEqual(first.record_hash, second.record_hash)
            self.assertEqual(first.evaluation_id, second.evaluation_id)
            self.assertEqual(len(evaluator.ledger.records()), 1)

            private_rows = (
                root
                / "authority-state"
                / "private_evaluations.jsonl"
            ).read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(private_rows), 1)

    def test_private_seed_never_enters_public_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evaluator = self.evaluator(root)
            decision = evaluator.evaluate(
                capability="normalize_text",
                entrypoint="solve",
                baseline_source=BASELINE,
                finalist_source=NORMALIZER,
                required_score=1.0,
                minimum_gain=0.05,
            )
            self.assertIsNone(decision.seed)

            private = json.loads(
                (
                    root
                    / "authority-state"
                    / "private_evaluations.jsonl"
                )
                .read_text(encoding="utf-8")
                .strip()
            )
            public = json.loads(
                (
                    root
                    / "workspace"
                    / "protected_evaluator.jsonl"
                )
                .read_text(encoding="utf-8")
                .strip()
            )
            self.assertIsInstance(private["seed"], int)
            self.assertNotIn("seed", private["receipt"])
            self.assertIsNone(public["seed"])

    def test_hidden_suite_rejects_non_general_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evaluator = self.evaluator(root)
            decision = evaluator.evaluate(
                capability="normalize_text",
                entrypoint="solve",
                baseline_source=BASELINE,
                finalist_source=(
                    "def solve(x0):\n"
                    "    return x0\n"
                ),
                required_score=1.0,
                minimum_gain=0.05,
            )
            self.assertFalse(decision.passed)
            self.assertEqual(
                decision.reason,
                "hidden_suite_below_required_score",
            )

    def test_threshold_change_cannot_redraw_hidden_suite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evaluator = self.evaluator(root)
            evaluator.evaluate(
                capability="normalize_text",
                entrypoint="solve",
                baseline_source=BASELINE,
                finalist_source=NORMALIZER,
                required_score=1.0,
                minimum_gain=0.05,
            )
            with self.assertRaisesRegex(
                ValueError,
                "different acceptance thresholds",
            ):
                evaluator.evaluate(
                    capability="normalize_text",
                    entrypoint="solve",
                    baseline_source=BASELINE,
                    finalist_source=NORMALIZER,
                    required_score=0.9,
                    minimum_gain=0.05,
                )
            private_rows = (
                root
                / "authority-state"
                / "private_evaluations.jsonl"
            ).read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(private_rows), 1)

    def test_explicit_wrong_trust_pin_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evaluator = ProtectedEvaluator(
                root / "workspace",
                authority_state=root / "authority-state",
                trusted_public_key_sha256="0" * 64,
                authority_mode="process",
            )
            with self.assertRaisesRegex(
                ValueError,
                "configured trust pin",
            ):
                evaluator.evaluate(
                    capability="normalize_text",
                    entrypoint="solve",
                    baseline_source=BASELINE,
                    finalist_source=NORMALIZER,
                    required_score=1.0,
                    minimum_gain=0.05,
                )

    def test_custom_capability_has_no_invented_hidden_distribution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evaluator = self.evaluator(root)
            decision = evaluator.evaluate(
                capability="custom_unknown",
                entrypoint="solve",
                baseline_source=BASELINE,
                finalist_source=NORMALIZER,
                required_score=1.0,
                minimum_gain=0.05,
            )
            self.assertIsNone(decision)
            self.assertFalse(
                (
                    root
                    / "workspace"
                    / "protected_evaluator.jsonl"
                ).exists()
            )
            self.assertFalse(
                (root / "authority-state").exists()
            )

    def test_tampered_public_evidence_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evaluator = self.evaluator(root)
            evaluator.evaluate(
                capability="normalize_text",
                entrypoint="solve",
                baseline_source=BASELINE,
                finalist_source=NORMALIZER,
                required_score=1.0,
                minimum_gain=0.05,
            )
            path = (
                root
                / "workspace"
                / "protected_evaluator.jsonl"
            )
            row = json.loads(
                path.read_text(encoding="utf-8").strip()
            )
            row["finalist_score"] = 0.0
            path.write_text(
                json.dumps(row) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                ValueError,
                "record hash mismatch",
            ):
                ProtectedEvaluationLedger(
                    root / "workspace"
                ).records()


if __name__ == "__main__":
    unittest.main()
