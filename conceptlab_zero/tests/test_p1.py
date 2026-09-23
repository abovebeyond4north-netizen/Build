from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from conceptlab import HIDDEN_PRINCIPLES, run_campaign
from p1 import (
    ABLATION_FRACTION_GATE,
    COUNTERFACTUAL_GATE,
    build_counterfactual_cases,
    run_p1,
    verify_p1,
)


class ConceptLabP1Tests(unittest.TestCase):
    def test_counterfactual_generator_balances_changed_and_unchanged(self) -> None:
        for index, (_opaque_id, hidden) in enumerate(HIDDEN_PRINCIPLES):
            cases = build_counterfactual_cases(
                hidden=hidden,
                seed=7000 + index,
                count=64,
            )
            changed = sum(case.expected_changed for case in cases)
            unchanged = len(cases) - changed
            self.assertEqual(changed, 32)
            self.assertEqual(unchanged, 32)

    def test_p1_counterfactual_and_ablation_gates(self) -> None:
        with tempfile.TemporaryDirectory(prefix="conceptlab-p1-") as directory:
            workspace = Path(directory)
            p0 = run_campaign(workspace)
            self.assertTrue(p0.all_p0_gates_passed)

            p1 = run_p1(workspace)
            self.assertTrue(p1.all_p1_gates_passed)
            self.assertFalse(p1.clg1_unlocked)
            self.assertEqual(p1.claim, "p1_causal_utility_passed")

            for result in p1.principle_results:
                self.assertTrue(result.passed, result.failure_reasons)
                self.assertGreaterEqual(
                    result.counterfactual_accuracy,
                    COUNTERFACTUAL_GATE,
                )
                self.assertEqual(result.counterfactual_cases, 64)
                self.assertEqual(result.capsule_score, 1.0)
                self.assertGreaterEqual(
                    result.ablation_fraction,
                    ABLATION_FRACTION_GATE,
                )
                self.assertGreater(
                    result.capsule_score,
                    result.ablated_score,
                )

            verified = verify_p1(workspace)
            self.assertEqual(
                verified.evidence_ledger_tip,
                p1.evidence_ledger_tip,
            )
            self.assertEqual(
                verified.p0_manifest_commitment,
                p0.manifest_commitment,
            )


if __name__ == "__main__":
    unittest.main()
