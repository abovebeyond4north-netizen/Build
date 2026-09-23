from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from conceptlab import run_campaign
from p1 import run_p1
from p2 import run_p2
from p3 import run_p3
from p4 import run_p4
from p5 import FAMILY_SPECS, run_p5
from p6 import (
    D8_ACCURACY_GATE,
    EFFICIENCY_RATIO_GATE,
    MAX_ACTIVE_QUERIES,
    generate_active_pool,
    run_p6,
    verify_p6,
)
from p6_learner import enumerate_candidates


class ConceptLabP6Tests(unittest.TestCase):
    def test_active_pools_contain_discriminative_and_ambiguous_examples(self) -> None:
        for spec in FAMILY_SPECS:
            pool = generate_active_pool(spec=spec)
            candidates = enumerate_candidates(
                family_id=spec.family_id,
                raw_observations=tuple(
                    episode.raw for episode in pool
                ),
            )
            self.assertGreater(len(candidates), 1)
            self.assertEqual(len(pool), 256)

    def test_p6_active_curriculum(self) -> None:
        with tempfile.TemporaryDirectory(prefix="conceptlab-p6-") as directory:
            workspace = Path(directory)
            self.assertTrue(run_campaign(workspace).all_p0_gates_passed)
            self.assertTrue(run_p1(workspace).all_p1_gates_passed)
            self.assertTrue(run_p2(workspace).all_p2_gates_passed)
            self.assertTrue(run_p3(workspace).all_p3_gates_passed)
            self.assertTrue(run_p4(workspace).all_p4_gates_passed)
            self.assertTrue(run_p5(workspace).all_p5_gates_passed)

            p6 = run_p6(workspace)
            self.assertTrue(p6.all_p6_gates_passed)
            self.assertFalse(p6.clg1_unlocked)
            self.assertTrue(p6.controller_unchanged)
            self.assertEqual(p6.claim, "p6_active_curriculum_passed")

            for result in p6.curriculum_results:
                self.assertTrue(result.passed, result.failure_reasons)
                self.assertLessEqual(
                    result.active_queries,
                    MAX_ACTIVE_QUERIES,
                )
                self.assertGreaterEqual(
                    result.efficiency_ratio,
                    EFFICIENCY_RATIO_GATE,
                )
                self.assertGreaterEqual(
                    result.d8_accuracy,
                    D8_ACCURACY_GATE,
                )
                self.assertTrue(result.all_queries_discriminative)
                self.assertTrue(result.exact_feature_recovery)
                self.assertTrue(result.queried_indices_unique)

            verified = verify_p6(workspace)
            self.assertEqual(
                verified.evidence_ledger_tip,
                p6.evidence_ledger_tip,
            )


if __name__ == "__main__":
    unittest.main()
