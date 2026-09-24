from __future__ import annotations

import unittest

from adi_genesis12 import (
    ArchitectureViolation,
    DecisionAlignedPlanner,
    DeterministicHypothesisUniverse,
    assert_genesis12_architecture,
    policy_expected_cost,
    snapshot_from_payloads,
)


class ArchitectureContractTests(unittest.TestCase):
    def _payloads(self):
        return {
            "base_model": b"genesis9-base-rd",
            "specialist_model": b"genesis9-specialist-l",
            "broad_model": b"genesis9-broad-fallback",
            "evaluator": b"protected-evaluator-v1",
            "promotion": b"evidence-gated-promotion-v1",
            "memory": b"modular-memory-v1",
            "distributions": b"e0-e1-e2-e3-frozen",
            "planner": b"genesis9-hard-routing-query-policy",
        }

    def test_only_planner_may_change(self):
        before_payloads = self._payloads()
        after_payloads = dict(before_payloads)
        after_payloads["planner"] = b"genesis12-expected-stopping-time-policy"
        before = snapshot_from_payloads(before_payloads, label="before")
        after = snapshot_from_payloads(after_payloads, label="after")
        assert_genesis12_architecture(before, after)

    def test_frozen_component_change_fails_closed(self):
        before_payloads = self._payloads()
        after_payloads = dict(before_payloads)
        after_payloads["planner"] = b"genesis12-expected-stopping-time-policy"
        after_payloads["evaluator"] = b"changed-evaluator"
        before = snapshot_from_payloads(before_payloads, label="before")
        after = snapshot_from_payloads(after_payloads, label="after")
        with self.assertRaises(ArchitectureViolation):
            assert_genesis12_architecture(before, after)

    def test_no_planner_change_is_not_genesis12(self):
        before = snapshot_from_payloads(self._payloads(), label="before")
        after = snapshot_from_payloads(self._payloads(), label="after")
        with self.assertRaises(ArchitectureViolation):
            assert_genesis12_architecture(before, after)


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.world = DeterministicHypothesisUniverse(
            hypothesis_ids=("h0", "h1", "h2", "h3", "h4", "h5"),
            action_ids=("a0", "a1", "a2", "a3"),
            predictions=(
                (0, 0, 0, 1),
                (1, 0, 0, 1),
                (0, 0, 1, 0),
                (1, 1, 1, 0),
                (0, 1, 1, 1),
                (0, 0, 1, 1),
            ),
            prior=(1, 1, 1, 1, 1, 1),
        )

    def test_exact_planner_beats_entropy_on_stopping_time(self):
        planner = DecisionAlignedPlanner(self.world)
        decision = planner.select_action()
        self.assertEqual(decision.action_id, "a1")
        self.assertAlmostEqual(decision.expected_remaining_probes, 8 / 3, places=12)

        exact_cost = policy_expected_cost(
            self.world,
            lambda state: DecisionAlignedPlanner(self.world).select_action(state).action_index,
        )
        entropy_cost = policy_expected_cost(self.world, planner.entropy_greedy_action)
        self.assertAlmostEqual(exact_cost, 8 / 3, places=12)
        self.assertAlmostEqual(entropy_cost, 17 / 6, places=12)
        self.assertLess(exact_cost, entropy_cost)

    def test_budget_exhaustion_falls_back_without_model_change(self):
        planner = DecisionAlignedPlanner(self.world, max_states=1, max_hypothesis_ops=10_000)
        decision = planner.select_action()
        self.assertTrue(decision.stats.used_fallback)
        self.assertEqual(decision.action_index, planner.entropy_greedy_action())
        self.assertIsNone(decision.expected_remaining_probes)

    def test_resource_accounting_is_populated(self):
        planner = DecisionAlignedPlanner(self.world)
        decision = planner.select_action()
        self.assertGreater(decision.stats.states_expanded, 0)
        self.assertGreater(decision.stats.hypothesis_ops, 0)
        self.assertGreater(decision.stats.branch_evaluations, 0)
        self.assertGreater(decision.stats.cpu_ns, 0)
        self.assertGreaterEqual(decision.stats.peak_traced_bytes, 0)

    def test_nondiscriminating_universe_fails(self):
        world = DeterministicHypothesisUniverse(
            hypothesis_ids=("h0", "h1"),
            action_ids=("a0",),
            predictions=((0,), (0,)),
            prior=(0.5, 0.5),
        )
        with self.assertRaises(ValueError):
            DecisionAlignedPlanner(world).select_action()


if __name__ == "__main__":
    unittest.main()
