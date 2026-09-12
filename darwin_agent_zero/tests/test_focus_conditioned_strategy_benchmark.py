import tempfile
import unittest
from pathlib import Path

from dgm_zero.strategy_benchmark import (
    BENCHMARK_FOCI,
    FocusConditionedDarwinAgent,
    cognitive_state_for_focus,
    run_strategy_benchmark,
    validate_focus,
)


class FocusConditionedStrategyBenchmarkTests(unittest.TestCase):
    def test_every_supported_focus_has_a_matching_bounded_state(self):
        for focus in BENCHMARK_FOCI:
            with self.subTest(focus=focus):
                state = cognitive_state_for_focus(focus)
                self.assertEqual(state.focus, focus)
                for value in (
                    state.confidence,
                    state.uncertainty,
                    state.stagnation,
                    state.diversity,
                    state.safety_pressure,
                ):
                    self.assertGreaterEqual(value, 0.0)
                    self.assertLessEqual(value, 1.0)

    def test_forced_focus_is_benchmark_only_and_stable(self):
        agent = FocusConditionedDarwinAgent.__new__(FocusConditionedDarwinAgent)
        agent._benchmark_focus = "escape stagnation"
        first = agent.assess_self()
        second = agent.assess_self()
        self.assertEqual(first, second)
        self.assertEqual(first.focus, "escape stagnation")
        self.assertGreater(first.stagnation, 0.70)

    def test_small_benchmark_report_commits_to_focus(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = run_strategy_benchmark(
                Path(tmp) / "workspace",
                seeds=(101,),
                generations=1,
                population=2,
                focus="increase diversity",
            )
            self.assertEqual(report.focus, "increase diversity")
            self.assertEqual(report.seeds, (101,))
            self.assertEqual(len(report.runs), 1)

    def test_invalid_focus_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "unsupported benchmark focus"):
            validate_focus("rewrite evaluator")


if __name__ == "__main__":
    unittest.main()
