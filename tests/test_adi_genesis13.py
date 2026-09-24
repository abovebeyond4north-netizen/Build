from __future__ import annotations

import unittest

from adi_genesis13 import (
    ArchitectureViolation,
    RepresentationRegistry,
    assert_genesis13_architecture,
    evaluate_seed,
    snapshot_from_payloads,
)


class ArchitectureContractTests(unittest.TestCase):
    def _payloads(self):
        return {
            "protected_evaluator": b"protected-evaluator",
            "hidden_world_generator": b"hidden-world-generator-v1",
            "causal_control_genesis9": b"genesis9-control",
            "planner": b"frozen-planner",
            "memory": b"frozen-memory",
            "promotion_rules": b"frozen-promotion",
            "train_eval_split": b"frozen-split",
            "representation_encoder": b"symbolic-shadow",
        }

    def test_only_representation_encoder_may_change(self):
        before_payloads = self._payloads()
        after_payloads = dict(before_payloads)
        after_payloads["representation_encoder"] = b"intervention-aligned-encoder"
        assert_genesis13_architecture(
            snapshot_from_payloads(before_payloads, label="before"),
            snapshot_from_payloads(after_payloads, label="after"),
        )

    def test_evaluator_mutation_fails_closed(self):
        before_payloads = self._payloads()
        after_payloads = dict(before_payloads)
        after_payloads["representation_encoder"] = b"intervention-aligned-encoder"
        after_payloads["protected_evaluator"] = b"mutated-evaluator"
        with self.assertRaises(ArchitectureViolation):
            assert_genesis13_architecture(
                snapshot_from_payloads(before_payloads, label="before"),
                snapshot_from_payloads(after_payloads, label="after"),
            )


class RepresentationRegistryTests(unittest.TestCase):
    def test_worse_candidate_rolls_back_by_nonpromotion(self):
        registry = RepresentationRegistry(
            active_version="v1",
            active_validation_error=0.10,
        )
        accepted = registry.propose(version="bad", validation_error=0.11)
        self.assertFalse(accepted)
        self.assertEqual(registry.active_version, "v1")
        self.assertEqual(registry.active_validation_error, 0.10)

    def test_better_candidate_promotes(self):
        registry = RepresentationRegistry(
            active_version="v1",
            active_validation_error=0.10,
        )
        accepted = registry.propose(version="v2", validation_error=0.08)
        self.assertTrue(accepted)
        self.assertEqual(registry.active_version, "v2")


class PilotMechanismTests(unittest.TestCase):
    def test_pilot_seed_shows_low_shot_transfer_and_causal_credit(self):
        result = evaluate_seed(42, pairs_per_action=1)
        self.assertGreater(result.improvement_vs_pooled, 0.60)
        self.assertGreater(result.improvement_vs_fewshot, 0.40)
        self.assertGreater(result.shuffled_to_candidate_ratio, 2.0)
        self.assertGreaterEqual(result.structure_f1, 0.95)
        self.assertGreaterEqual(result.compression_ratio, 2.5)

    def test_deterministic_replay(self):
        first = evaluate_seed(314, pairs_per_action=1)
        second = evaluate_seed(314, pairs_per_action=1)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
