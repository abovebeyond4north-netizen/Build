import tempfile
import unittest
from pathlib import Path

from dgm_zero.archive import Archive
from dgm_zero.benchmark import (
    BenchmarkResult,
    canonical_cases,
    evaluate_expression,
    expression_structural_cost,
)
from dgm_zero.oracle import EVALUATION_PROTOCOL_VERSION, EmpiricalGodelOracle


class DeterministicEfficiencyTests(unittest.TestCase):
    def test_structural_efficiency_ignores_wall_clock_variation(self):
        fast = BenchmarkResult(
            passed=1,
            total=1,
            elapsed_seconds=0.0001,
            errors=[],
            structural_cost=12,
        )
        slow = BenchmarkResult(
            passed=1,
            total=1,
            elapsed_seconds=999.0,
            errors=[],
            structural_cost=12,
        )
        self.assertEqual(fast.efficiency, slow.efficiency)

    def test_simpler_expression_has_lower_cost_and_higher_efficiency(self):
        simple = "a + b"
        complex_expression = "a * a + 3 * b - gcd(a, b)"
        self.assertLess(
            expression_structural_cost(simple),
            expression_structural_cost(complex_expression),
        )
        cases = canonical_cases(count=8)
        simple_result = evaluate_expression(simple, cases)
        complex_result = evaluate_expression(complex_expression, cases)
        self.assertGreater(simple_result.efficiency, complex_result.efficiency)

    def test_repeated_evaluation_has_identical_efficiency(self):
        expression = "a * a + 3 * b - gcd(a, b)"
        cases = canonical_cases(seed=31, count=16)
        first = evaluate_expression(expression, cases)
        second = evaluate_expression(expression, cases)
        self.assertEqual(first.structural_cost, second.structural_cost)
        self.assertEqual(first.efficiency, second.efficiency)
        self.assertEqual(first.correctness, second.correctness)

    def test_oracle_score_is_repeatable_with_same_frozen_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Archive(Path(tmp))
            oracle = EmpiricalGodelOracle(archive)
            expression = "a * a + 3 * b - gcd(a, b)"
            first = oracle.judge(expression)
            second = oracle.judge(expression)
            self.assertEqual(first.evaluation_context, second.evaluation_context)
            self.assertEqual(first.score.as_dict(), second.score.as_dict())

    def test_legacy_result_without_structural_cost_retains_timing_semantics(self):
        fast = BenchmarkResult(1, 1, 0.1, [])
        slow = BenchmarkResult(1, 1, 1.0, [])
        self.assertGreater(fast.efficiency, slow.efficiency)

    def test_invalid_expression_receives_bounded_deterministic_cost(self):
        result = evaluate_expression("a +", canonical_cases(count=2))
        self.assertGreater(result.structural_cost or 0, 0)
        self.assertGreaterEqual(result.efficiency, 0.0)
        self.assertLessEqual(result.efficiency, 1.0)

    def test_oracle_protocol_version_marks_new_scoring_semantics(self):
        self.assertEqual(EVALUATION_PROTOCOL_VERSION, 2)


if __name__ == "__main__":
    unittest.main()
