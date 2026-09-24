from __future__ import annotations

import unittest
import numpy as np

from adi_genesis15.confirmatory import gates
from adi_genesis15.experiment import (
    ACTION_COUNT, LATENT_DIM, BaseDynamics, action_vector,
    fit_base_dynamics, collect_full_rollout, random_mask,
)

class Genesis15ArchitectureTests(unittest.TestCase):
    def test_action_interface_is_bounded(self):
        self.assertEqual(ACTION_COUNT, LATENT_DIM + 1)
        for i in range(ACTION_COUNT):
            self.assertEqual(action_vector(i).shape, (LATENT_DIM,))
        with self.assertRaises(ValueError):
            action_vector(ACTION_COUNT)

    def test_partial_observation_hides_one_coordinate(self):
        rng=np.random.default_rng(7)
        for _ in range(20):
            self.assertEqual(int(np.sum(random_mask(rng))), LATENT_DIM-1)

    def test_base_model_fit_is_finite(self):
        rng=np.random.default_rng(11)
        model=fit_base_dynamics([collect_full_rollout(rng, steps=80)])
        self.assertIsInstance(model, BaseDynamics)
        self.assertTrue(np.isfinite(model.A).all())
        self.assertTrue(np.isfinite(model.Q).all())

    def test_gate_fails_closed(self):
        bad={
            "n_seeds":20.0,"multistep_candidate_rmse":1.0,"multistep_raw_rmse":1.0,
            "multistep_improvement_vs_raw":0.0,"planning_candidate_regret":1.0,
            "planning_raw_regret":1.0,"planning_regret_improvement_vs_raw":0.0,
            "coverage_90":0.5,"interval_width_90":1.0,"shift_detection_rate":0.0,
            "false_positive_rate":1.0,"mean_detection_delay":65.0,
            "adapted_candidate_rmse":1.0,"unadapted_candidate_rmse":1.0,
            "adapted_raw_rmse":1.0,"adaptation_improvement_vs_unadapted":0.0,
            "adaptation_improvement_vs_raw":0.0,
        }
        self.assertFalse(all(gates(bad).values()))

if __name__ == "__main__":
    unittest.main()
