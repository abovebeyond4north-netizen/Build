import unittest

from dgm_zero.self_patch import compare_strategy_reports


SEEDS = [11, 23, 47]


def report(aggregate, mean, champions):
    return {
        "seeds": list(SEEDS),
        "aggregate_score": aggregate,
        "mean_champion_score": mean,
        "worst_champion_score": min(champions),
        "runs": [
            {"seed": seed, "champion_score": score}
            for seed, score in zip(SEEDS, champions)
        ],
    }


class PatchStrategyComparisonTests(unittest.TestCase):
    def test_equal_deterministic_results_pass(self):
        baseline = report(0.70, 0.80, [0.80, 0.79, 0.81])
        comparison = compare_strategy_reports(baseline, dict(baseline))
        self.assertTrue(comparison.passed)
        self.assertEqual(comparison.aggregate_delta, 0.0)
        self.assertEqual(comparison.worst_seed_champion_delta, 0.0)

    def test_aggregate_regression_fails(self):
        baseline = report(0.70, 0.80, [0.80, 0.79, 0.81])
        candidate = report(0.69, 0.80, [0.80, 0.79, 0.81])
        comparison = compare_strategy_reports(baseline, candidate)
        self.assertFalse(comparison.passed)
        self.assertTrue(any("aggregate" in reason for reason in comparison.reasons))

    def test_mean_champion_regression_cannot_be_hidden_by_other_metrics(self):
        baseline = report(0.70, 0.80, [0.80, 0.79, 0.81])
        candidate = report(0.72, 0.79, [0.79, 0.78, 0.80])
        comparison = compare_strategy_reports(baseline, candidate)
        self.assertFalse(comparison.passed)
        self.assertTrue(any("mean champion" in reason for reason in comparison.reasons))

    def test_large_single_seed_regression_fails(self):
        baseline = report(0.70, 0.80, [0.80, 0.79, 0.81])
        candidate = report(0.71, 0.80, [0.83, 0.82, 0.78])
        comparison = compare_strategy_reports(baseline, candidate)
        self.assertFalse(comparison.passed)
        self.assertTrue(any("seed 47" in reason for reason in comparison.reasons))

    def test_seed_set_mismatch_fails_closed(self):
        baseline = report(0.70, 0.80, [0.80, 0.79, 0.81])
        candidate = dict(baseline)
        candidate["seeds"] = [11, 23, 99]
        with self.assertRaisesRegex(ValueError, "seeds do not match"):
            compare_strategy_reports(baseline, candidate)


if __name__ == "__main__":
    unittest.main()
