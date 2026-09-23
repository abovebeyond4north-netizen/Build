from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from conceptlab import run_campaign
from p1 import run_p1
from p2 import run_p2
from p3 import run_p3
from p4 import run_p4
from p5 import (
    CONTROL_GAIN_GATE,
    D7_ACCURACY_GATE,
    FAMILY_SPECS,
    RESTART_GATE,
    SUPPORT_ACCURACY_GATE,
    TokenizationLearner,
    decoder_by_name,
    generate_raw_episodes,
    hidden_controller,
    run_p5,
    verify_p5,
)


class ConceptLabP5Tests(unittest.TestCase):
    def test_each_family_requires_decoder_and_slot_discovery(self) -> None:
        self.assertGreaterEqual(len(FAMILY_SPECS), 4)
        for spec in FAMILY_SPECS:
            self.assertGreaterEqual(spec.width, 6)
            self.assertNotEqual(spec.signal_indices, (0, 1))
            self.assertIsNotNone(decoder_by_name(spec.decoder_name))

    def test_tokenization_search_recovers_hidden_structure(self) -> None:
        spec = FAMILY_SPECS[0]
        support = generate_raw_episodes(
            spec=spec,
            seed=spec.seed,
            count=48,
            low=-48,
            high=48,
        )
        feature, accuracy, _runner, _runner_accuracy, searched = (
            TokenizationLearner().fit(
                controller=hidden_controller(spec.target_id),
                family_id=spec.family_id,
                episodes=support,
            )
        )
        self.assertGreaterEqual(accuracy, SUPPORT_ACCURACY_GATE)
        self.assertEqual(feature.decoder_name, spec.decoder_name)
        self.assertEqual(
            (feature.left_index, feature.right_index),
            spec.signal_indices,
        )
        self.assertGreater(searched, 10)

    def test_p5_raw_token_and_slot_discovery(self) -> None:
        with tempfile.TemporaryDirectory(prefix="conceptlab-p5-") as directory:
            workspace = Path(directory)
            self.assertTrue(run_campaign(workspace).all_p0_gates_passed)
            self.assertTrue(run_p1(workspace).all_p1_gates_passed)
            self.assertTrue(run_p2(workspace).all_p2_gates_passed)
            self.assertTrue(run_p3(workspace).all_p3_gates_passed)
            self.assertTrue(run_p4(workspace).all_p4_gates_passed)

            p5 = run_p5(workspace)
            self.assertTrue(p5.all_p5_gates_passed)
            self.assertFalse(p5.clg1_unlocked)
            self.assertTrue(p5.controllers_unchanged)
            self.assertEqual(
                p5.claim,
                "p5_raw_token_and_slot_discovery_passed",
            )
            self.assertEqual(len(p5.family_results), len(FAMILY_SPECS))
            for result in p5.family_results:
                self.assertTrue(result.passed, result.failure_reasons)
                self.assertGreaterEqual(
                    result.support_accuracy,
                    SUPPORT_ACCURACY_GATE,
                )
                self.assertGreaterEqual(
                    result.d7_accuracy,
                    D7_ACCURACY_GATE,
                )
                self.assertGreaterEqual(
                    result.control_gain,
                    CONTROL_GAIN_GATE,
                )
                self.assertEqual(result.structural_collisions, 0)
                self.assertGreaterEqual(
                    result.restart_accuracy,
                    RESTART_GATE,
                )
                self.assertEqual(result.support_cases, 48)
                self.assertEqual(result.holdout_cases, 200)

            verified = verify_p5(workspace)
            self.assertEqual(
                verified.evidence_ledger_tip,
                p5.evidence_ledger_tip,
            )


if __name__ == "__main__":
    unittest.main()
