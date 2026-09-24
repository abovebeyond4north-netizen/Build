from __future__ import annotations

import unittest

import numpy as np

from adi_genesis13.experiment import LATENT_DIM, TRUE_B
from adi_genesis14 import (
    ArchitectureViolation,
    assert_genesis14_architecture,
    evaluate_seed,
    snapshot_from_payloads,
)
from adi_genesis14.experiment import fit_latent_residual


class ArchitectureContractTests(unittest.TestCase):
    def _payloads(self):
        return {
            "protected_evaluator": b"protected-evaluator",
            "hidden_world_generator": b"world-generator",
            "representation_genesis13": b"validated-genesis13",
            "causal_control_genesis9": b"genesis9-control",
            "memory": b"frozen-memory",
            "promotion_rules": b"frozen-promotion",
            "train_eval_split": b"frozen-split",
            "latent_dynamics_model": b"no-world-model",
            "residual_adapter": b"no-residual-adapter",
        }

    def test_only_world_model_components_may_change(self):
        before_payloads = self._payloads()
        after_payloads = dict(before_payloads)
        after_payloads["latent_dynamics_model"] = b"shared-latent-dynamics"
        after_payloads["residual_adapter"] = b"latent-residual-v1"
        assert_genesis14_architecture(
            snapshot_from_payloads(before_payloads, label="before"),
            snapshot_from_payloads(after_payloads, label="after"),
        )

    def test_representation_mutation_fails_closed(self):
        before_payloads = self._payloads()
        after_payloads = dict(before_payloads)
        after_payloads["latent_dynamics_model"] = b"shared-latent-dynamics"
        after_payloads["representation_genesis13"] = b"mutated-representation"
        with self.assertRaises(ArchitectureViolation):
            assert_genesis14_architecture(
                snapshot_from_payloads(before_payloads, label="before"),
                snapshot_from_payloads(after_payloads, label="after"),
            )


class ResidualAdapterTests(unittest.TestCase):
    def test_residual_adapter_preserves_action_effect_rows(self):
        rng = np.random.default_rng(123)
        base = rng.normal(size=(2 * LATENT_DIM + 1, LATENT_DIM))

        class Diagnostic:
            estimated_mixing = np.vstack(
                [
                    np.eye(LATENT_DIM),
                    np.zeros((5, LATENT_DIM)),
                ]
            )

        n = 12
        x = rng.normal(size=(n, 8))
        action = np.eye(LATENT_DIM)[rng.integers(0, LATENT_DIM, size=n)]
        y = rng.normal(size=(n, 8))

        class Batch:
            pass

        batch = Batch()
        batch.x = x
        batch.action = action
        batch.y = y

        adapted = fit_latent_residual(base, Diagnostic(), batch)
        np.testing.assert_allclose(
            adapted[LATENT_DIM : 2 * LATENT_DIM, :],
            base[LATENT_DIM : 2 * LATENT_DIM, :],
        )


class PilotMechanismTests(unittest.TestCase):
    def test_pilot_seed_shows_downstream_sufficiency(self):
        result = evaluate_seed(42, shift_adaptation_steps=8)
        self.assertGreater(result.multistep_improvement_vs_raw, 0.60)
        self.assertGreater(result.planning_regret_improvement_vs_raw, 0.60)
        self.assertGreater(result.exploitation_gap_improvement_vs_raw, 0.50)
        self.assertGreater(result.shift_improvement_vs_unadapted, 0.05)

    def test_deterministic_replay(self):
        first = evaluate_seed(314, shift_adaptation_steps=8)
        second = evaluate_seed(314, shift_adaptation_steps=8)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
