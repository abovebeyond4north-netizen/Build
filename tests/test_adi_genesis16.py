from __future__ import annotations

import unittest
import numpy as np

from adi_genesis16.confirmatory import gates
from adi_genesis16.contract import (
    ArchitectureViolation,
    assert_genesis16_architecture,
    snapshot_from_payloads,
)
from adi_genesis16.experiment import (
    BASE_COEFFICIENTS,
    EnsembleDynamics,
    action_vector,
    ensemble_mean_predict,
    ensemble_predict,
    hidden_step,
    no_epistemic_predict,
)
from adi_genesis13.experiment import TRUE_A, TRUE_B


class Genesis16ArchitectureTests(unittest.TestCase):
    def _payloads(self):
        return {
            "protected_evaluator": b"protected-evaluator",
            "hidden_world_generator_genesis16": b"frozen-nonlinear-worlds",
            "representation_genesis13": b"genesis13-frozen",
            "partial_observation_interface_genesis15": b"genesis15-partial-observation",
            "measurement_update_genesis15": b"genesis15-measurement-update",
            "causal_control_genesis9": b"genesis9-frozen",
            "memory": b"memory-frozen",
            "promotion_rules": b"promotion-frozen",
            "train_eval_split": b"split-frozen",
            "planning_protocol": b"planning-frozen",
            "nonlinear_dynamics_model": b"linear-control",
            "uncertainty_ensemble": b"no-ensemble",
            "shift_detector": b"genesis15-detector",
        }

    def test_only_genesis16_components_may_change(self):
        before = self._payloads()
        after = dict(before)
        after["nonlinear_dynamics_model"] = b"nonlinear-basis-v1"
        after["uncertainty_ensemble"] = b"bootstrap-ensemble-v1"
        after["shift_detector"] = b"ensemble-innovation-v1"
        assert_genesis16_architecture(
            snapshot_from_payloads(before, label="before"),
            snapshot_from_payloads(after, label="after"),
        )

    def test_parent_representation_mutation_fails_closed(self):
        before = self._payloads()
        after = dict(before)
        after["nonlinear_dynamics_model"] = b"nonlinear-basis-v1"
        after["representation_genesis13"] = b"mutated-representation"
        with self.assertRaises(ArchitectureViolation):
            assert_genesis16_architecture(
                snapshot_from_payloads(before, label="before"),
                snapshot_from_payloads(after, label="after"),
            )

    def test_partial_observation_interface_mutation_fails_closed(self):
        before = self._payloads()
        after = dict(before)
        after["nonlinear_dynamics_model"] = b"nonlinear-basis-v1"
        after["partial_observation_interface_genesis15"] = b"easier-observation"
        with self.assertRaises(ArchitectureViolation):
            assert_genesis16_architecture(
                snapshot_from_payloads(before, label="before"),
                snapshot_from_payloads(after, label="after"),
            )

    def test_evaluator_mutation_fails_closed(self):
        before = self._payloads()
        after = dict(before)
        after["uncertainty_ensemble"] = b"bootstrap-ensemble-v1"
        after["protected_evaluator"] = b"mutated-evaluator"
        with self.assertRaises(ArchitectureViolation):
            assert_genesis16_architecture(
                snapshot_from_payloads(before, label="before"),
                snapshot_from_payloads(after, label="after"),
            )

    def test_no_experimental_change_fails_closed(self):
        payloads = self._payloads()
        with self.assertRaises(ArchitectureViolation):
            assert_genesis16_architecture(
                snapshot_from_payloads(payloads, label="before"),
                snapshot_from_payloads(payloads, label="after"),
            )


class MechanismAblationTests(unittest.TestCase):
    def _model(self) -> EnsembleDynamics:
        rng = np.random.default_rng(17)
        feature_count = 3 + 12 + 3 + 1
        weights = rng.normal(scale=0.05, size=(5, feature_count, 3))
        Q = np.stack([np.eye(3) * (0.01 + i * 0.001) for i in range(5)])
        return EnsembleDynamics(
            weights=weights,
            Q=Q,
            mean_weights=weights.mean(axis=0),
        )

    def test_no_epistemic_ablation_preserves_predictive_mean(self):
        model = self._model()
        state = np.array([0.2, -0.3, 0.4])
        action = action_vector(1)
        ensemble_mean, ensemble_covariance = ensemble_predict(
            model, state, action
        )
        ablated_mean, ablated_covariance = no_epistemic_predict(
            model, state, action
        )
        np.testing.assert_allclose(ensemble_mean, ablated_mean)
        self.assertGreaterEqual(
            float(np.trace(ensemble_covariance)),
            float(np.trace(ablated_covariance)),
        )

    def test_fast_mean_path_matches_full_ensemble_mean(self):
        model = self._model()
        state = np.array([-0.1, 0.5, 0.25])
        action = action_vector(2)
        np.testing.assert_allclose(
            ensemble_mean_predict(model, state, action),
            ensemble_predict(model, state, action)[0],
        )

    def test_nonlinear_world_is_not_linear_control(self):
        state = np.array([0.7, -0.8, 0.6])
        action = action_vector(0)
        nonlinear = hidden_step(
            state,
            action,
            coefficients=BASE_COEFFICIENTS,
        )
        linear = TRUE_A @ state + TRUE_B @ action
        self.assertGreater(float(np.linalg.norm(nonlinear - linear)), 0.01)


class PromotionGateTests(unittest.TestCase):
    def test_bad_result_fails_closed(self):
        bad = {
            "n_seeds": 20.0,
            "multistep_candidate_rmse": 1.0,
            "multistep_linear_rmse": 1.0,
            "multistep_improvement_vs_linear": 0.0,
            "planning_candidate_regret": 1.0,
            "planning_linear_regret": 1.0,
            "planning_improvement_vs_linear": 0.0,
            "coverage_90": 0.50,
            "interval_width_90": 1.0,
            "gaussian_nll": 1.0,
            "no_epistemic_nll": 1.0,
            "nll_gain_vs_no_epistemic": 0.0,
            "abrupt_detection_rate": 0.0,
            "gradual_detection_rate": 0.0,
            "false_positive_rate": 1.0,
            "abrupt_detection_delay": 75.0,
            "gradual_detection_delay": 75.0,
            "candidate_compute_seconds": 100.0,
            "linear_compute_seconds": 1.0,
            "compute_ratio": 100.0,
        }
        self.assertFalse(all(gates(bad).values()))


if __name__ == "__main__":
    unittest.main()
