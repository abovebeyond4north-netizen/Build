from __future__ import annotations

import unittest
import numpy as np

from adi_genesis15.confirmatory import gates
from adi_genesis15.contract import (
    ArchitectureViolation,
    assert_genesis15_architecture,
    snapshot_from_payloads,
)
from adi_genesis15.experiment import (
    ACTION_COUNT,
    LATENT_DIM,
    BaseDynamics,
    action_vector,
    collect_full_rollout,
    detect_shift,
    fit_base_dynamics,
    random_mask,
)


class Genesis15ArchitectureTests(unittest.TestCase):
    def _payloads(self):
        return {
            "protected_evaluator": b"protected-evaluator",
            "hidden_world_generator": b"hidden-world-generator",
            "representation_genesis13": b"genesis13-frozen",
            "world_model_genesis14": b"genesis14-frozen",
            "causal_control_genesis9": b"genesis9-frozen",
            "memory": b"memory-frozen",
            "promotion_rules": b"promotion-frozen",
            "train_eval_split": b"split-frozen",
            "evaluation_controls": b"controls-frozen",
            "belief_filter": b"no-belief-filter",
            "uncertainty_detector": b"no-detector",
            "gated_residual_adapter": b"no-adapter",
        }

    def test_only_genesis15_components_may_change(self):
        before = self._payloads()
        after = dict(before)
        after["belief_filter"] = b"partial-belief-v1"
        after["uncertainty_detector"] = b"innovation-gate-v1"
        after["gated_residual_adapter"] = b"smoothed-residual-v1"
        assert_genesis15_architecture(
            snapshot_from_payloads(before, label="before"),
            snapshot_from_payloads(after, label="after"),
        )

    def test_parent_world_model_mutation_fails_closed(self):
        before = self._payloads()
        after = dict(before)
        after["belief_filter"] = b"partial-belief-v1"
        after["world_model_genesis14"] = b"mutated-parent"
        with self.assertRaises(ArchitectureViolation):
            assert_genesis15_architecture(
                snapshot_from_payloads(before, label="before"),
                snapshot_from_payloads(after, label="after"),
            )

    def test_representation_mutation_fails_closed(self):
        before = self._payloads()
        after = dict(before)
        after["belief_filter"] = b"partial-belief-v1"
        after["representation_genesis13"] = b"mutated-representation"
        with self.assertRaises(ArchitectureViolation):
            assert_genesis15_architecture(
                snapshot_from_payloads(before, label="before"),
                snapshot_from_payloads(after, label="after"),
            )

    def test_evaluator_mutation_fails_closed(self):
        before = self._payloads()
        after = dict(before)
        after["belief_filter"] = b"partial-belief-v1"
        after["protected_evaluator"] = b"mutated-evaluator"
        with self.assertRaises(ArchitectureViolation):
            assert_genesis15_architecture(
                snapshot_from_payloads(before, label="before"),
                snapshot_from_payloads(after, label="after"),
            )

    def test_no_experimental_change_fails_closed(self):
        before = self._payloads()
        with self.assertRaises(ArchitectureViolation):
            assert_genesis15_architecture(
                snapshot_from_payloads(before, label="before"),
                snapshot_from_payloads(before, label="after"),
            )

    def test_action_interface_is_bounded(self):
        self.assertEqual(ACTION_COUNT, LATENT_DIM + 1)
        for i in range(ACTION_COUNT):
            self.assertEqual(action_vector(i).shape, (LATENT_DIM,))
        with self.assertRaises(ValueError):
            action_vector(ACTION_COUNT)

    def test_partial_observation_hides_one_coordinate(self):
        rng = np.random.default_rng(7)
        for _ in range(20):
            self.assertEqual(int(np.sum(random_mask(rng))), LATENT_DIM - 1)

    def test_base_model_fit_is_finite(self):
        rng = np.random.default_rng(11)
        model = fit_base_dynamics([collect_full_rollout(rng, steps=80)])
        self.assertIsInstance(model, BaseDynamics)
        self.assertTrue(np.isfinite(model.A).all())
        self.assertTrue(np.isfinite(model.Q).all())

    def test_no_shift_detector_abstains_on_fixed_control_seed(self):
        rng = np.random.default_rng(19)
        base = fit_base_dynamics(
            [collect_full_rollout(rng, steps=450) for _ in range(5)]
        )
        control_rng = np.random.default_rng(19001)
        self.assertIsNone(detect_shift(control_rng, base, shift=False))

    def test_gate_fails_closed(self):
        bad = {
            "n_seeds": 20.0,
            "multistep_candidate_rmse": 1.0,
            "multistep_raw_rmse": 1.0,
            "multistep_improvement_vs_raw": 0.0,
            "planning_candidate_regret": 1.0,
            "planning_raw_regret": 1.0,
            "planning_regret_improvement_vs_raw": 0.0,
            "coverage_90": 0.5,
            "interval_width_90": 1.0,
            "shift_detection_rate": 0.0,
            "false_positive_rate": 1.0,
            "mean_detection_delay": 65.0,
            "adapted_candidate_rmse": 1.0,
            "unadapted_candidate_rmse": 1.0,
            "adapted_raw_rmse": 1.0,
            "adaptation_improvement_vs_unadapted": 0.0,
            "adaptation_improvement_vs_raw": 0.0,
        }
        self.assertFalse(all(gates(bad).values()))


if __name__ == "__main__":
    unittest.main()
