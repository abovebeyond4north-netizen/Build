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


class ProtectedEvaluatorWorkerTests(unittest.TestCase):
    def test_hidden_suites_are_reproducible_per_seed_and_change_across_seeds(self):
        first = build_hidden_cases("normalize_text", 12345)
        repeat = build_hidden_cases("normalize_text", 12345)
        second = build_hidden_cases("normalize_text", 54321)
        self.assertEqual(first, repeat)
        self.assertNotEqual(first, second)
        self.assertEqual(len(first), 32)
        self.assertTrue(all(case.split == "holdout" for case in first))

    def test_containment_self_test_passes(self):
        passed, failures = containment_self_test()
        self.assertTrue(passed, failures)


class ProtectedEvaluatorTests(unittest.TestCase):
    def test_fresh_hidden_evaluation_passes_and_is_sealed(self):
        with tempfile.TemporaryDirectory() as tmp:
            evaluator = ProtectedEvaluator(Path(tmp))
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
            self.assertGreaterEqual(decision.delta, 0.05)
            self.assertEqual(decision.case_count, 32)
            self.assertTrue(decision.record_hash)

    def test_same_finalist_and_evaluator_version_reuses_one_shot_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            evaluator = ProtectedEvaluator(Path(tmp))
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
            self.assertEqual(first.seed, second.seed)
            self.assertEqual(len(evaluator.ledger.records()), 1)

    def test_hidden_suite_rejects_non_general_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            evaluator = ProtectedEvaluator(Path(tmp))
            decision = evaluator.evaluate(
                capability="normalize_text",
                entrypoint="solve",
                baseline_source=BASELINE,
                finalist_source="def solve(x0):\n    return x0\n",
                required_score=1.0,
                minimum_gain=0.05,
            )
            self.assertFalse(decision.passed)
            self.assertEqual(decision.reason, "hidden_suite_below_required_score")

    def test_custom_capability_has_no_invented_hidden_distribution(self):
        with tempfile.TemporaryDirectory() as tmp:
            evaluator = ProtectedEvaluator(Path(tmp))
            decision = evaluator.evaluate(
                capability="custom_unknown",
                entrypoint="solve",
                baseline_source=BASELINE,
                finalist_source=NORMALIZER,
                required_score=1.0,
                minimum_gain=0.05,
            )
            self.assertIsNone(decision)
            self.assertFalse((Path(tmp) / "protected_evaluator.jsonl").exists())

    def test_tampered_evidence_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            evaluator = ProtectedEvaluator(workspace)
            evaluator.evaluate(
                capability="normalize_text",
                entrypoint="solve",
                baseline_source=BASELINE,
                finalist_source=NORMALIZER,
                required_score=1.0,
                minimum_gain=0.05,
            )
            path = workspace / "protected_evaluator.jsonl"
            row = json.loads(path.read_text(encoding="utf-8").strip())
            row["finalist_score"] = 0.0
            path.write_text(json.dumps(row) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "record hash mismatch"):
                ProtectedEvaluationLedger(workspace).records()


if __name__ == "__main__":
    unittest.main()
