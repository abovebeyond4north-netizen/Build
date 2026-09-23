from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from conceptlab import GRAMMAR, run_campaign
from p1 import run_p1
from p2 import run_p2
from p3 import (
    COMPRESSION_GATE,
    D5_ACCURACY_GATE,
    P0_CONTROL_GAIN_GATE,
    RESTART_GATE,
    TRAIN_ACCURACY_GATE,
    HIDDEN_TARGETS,
    PROGRAM_GRAMMAR,
    SymbolicSynthesizer,
    generate_program_episodes,
    run_p3,
    verify_p3,
)


class ConceptLabP3Tests(unittest.TestCase):
    def test_hidden_targets_are_not_explicit_p0_rules(self) -> None:
        p0_signatures = {principle.signature for principle in GRAMMAR}
        for _target_id, target in HIDDEN_TARGETS:
            self.assertNotIn(target.signature, p0_signatures)

    def test_symbolic_search_constructs_nontrivial_program(self) -> None:
        target_id, hidden = HIDDEN_TARGETS[0]
        training = generate_program_episodes(
            hidden,
            domains=("list", "map"),
            seed=12345,
            count=96,
            low=-36,
            high=36,
        )
        program, accuracy, searched = SymbolicSynthesizer().fit(training)
        self.assertGreaterEqual(accuracy, TRAIN_ACCURACY_GATE)
        self.assertGreater(searched, 1000)
        self.assertIn(program, PROGRAM_GRAMMAR)
        self.assertNotEqual(program.signature, target_id)

    def test_p3_withheld_predicate_synthesis(self) -> None:
        with tempfile.TemporaryDirectory(prefix="conceptlab-p3-") as directory:
            workspace = Path(directory)
            self.assertTrue(run_campaign(workspace).all_p0_gates_passed)
            self.assertTrue(run_p1(workspace).all_p1_gates_passed)
            self.assertTrue(run_p2(workspace).all_p2_gates_passed)

            p3 = run_p3(workspace)
            self.assertTrue(p3.all_p3_gates_passed)
            self.assertFalse(p3.clg1_unlocked)
            self.assertEqual(
                p3.claim,
                "p3_withheld_predicate_synthesis_passed",
            )
            self.assertEqual(len(p3.synthesis_results), len(HIDDEN_TARGETS))
            for result in p3.synthesis_results:
                self.assertTrue(result.passed, result.failure_reasons)
                self.assertGreaterEqual(
                    result.train_accuracy,
                    TRAIN_ACCURACY_GATE,
                )
                self.assertGreaterEqual(
                    result.d5_accuracy,
                    D5_ACCURACY_GATE,
                )
                self.assertGreaterEqual(
                    result.p0_control_gain,
                    P0_CONTROL_GAIN_GATE,
                )
                self.assertGreaterEqual(
                    result.compression_ratio,
                    COMPRESSION_GATE,
                )
                self.assertEqual(result.structural_collisions, 0)
                self.assertGreaterEqual(
                    result.restart_accuracy,
                    RESTART_GATE,
                )

            verified = verify_p3(workspace)
            self.assertEqual(
                verified.evidence_ledger_tip,
                p3.evidence_ledger_tip,
            )


if __name__ == "__main__":
    unittest.main()
