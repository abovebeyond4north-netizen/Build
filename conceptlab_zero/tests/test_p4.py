from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from conceptlab import run_campaign
from p1 import run_p1
from p2 import run_p2
from p3 import run_p3
from p4 import (
    ADAPTATION_GAIN_GATE,
    D6_ACCURACY_GATE,
    DOMAIN_SPECS,
    RESTART_GATE,
    SUPPORT_ACCURACY_GATE,
    run_p4,
    verify_p4,
)


class ConceptLabP4Tests(unittest.TestCase):
    def test_domain_specs_require_nontrivial_ordered_adapters(self) -> None:
        for _domain_id, width, (left_index, right_index) in DOMAIN_SPECS:
            self.assertGreaterEqual(width, 6)
            self.assertNotEqual(left_index, right_index)
            self.assertNotEqual((left_index, right_index), (0, 1))

    def test_p4_adaptive_observation_interfaces(self) -> None:
        with tempfile.TemporaryDirectory(prefix="conceptlab-p4-") as directory:
            workspace = Path(directory)
            self.assertTrue(run_campaign(workspace).all_p0_gates_passed)
            self.assertTrue(run_p1(workspace).all_p1_gates_passed)
            self.assertTrue(run_p2(workspace).all_p2_gates_passed)
            self.assertTrue(run_p3(workspace).all_p3_gates_passed)

            p4 = run_p4(workspace)
            self.assertTrue(p4.all_p4_gates_passed)
            self.assertFalse(p4.clg1_unlocked)
            self.assertTrue(p4.controller_unchanged)
            self.assertEqual(
                p4.claim,
                "p4_adaptive_observation_interfaces_passed",
            )
            self.assertEqual(len(p4.domain_results), len(DOMAIN_SPECS))
            for result in p4.domain_results:
                self.assertTrue(result.passed, result.failure_reasons)
                self.assertGreaterEqual(
                    result.support_accuracy,
                    SUPPORT_ACCURACY_GATE,
                )
                self.assertGreaterEqual(
                    result.d6_accuracy,
                    D6_ACCURACY_GATE,
                )
                self.assertGreaterEqual(
                    result.adaptation_gain,
                    ADAPTATION_GAIN_GATE,
                )
                self.assertEqual(result.signal_pair_collisions, 0)
                self.assertGreaterEqual(
                    result.restart_accuracy,
                    RESTART_GATE,
                )
                self.assertEqual(result.support_cases, 32)
                self.assertEqual(result.holdout_cases, 160)

            verified = verify_p4(workspace)
            self.assertEqual(
                verified.evidence_ledger_tip,
                p4.evidence_ledger_tip,
            )


if __name__ == "__main__":
    unittest.main()
