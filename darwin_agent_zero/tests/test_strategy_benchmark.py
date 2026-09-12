import tempfile
import unittest
from pathlib import Path

from dgm_zero.strategy_benchmark import parse_seeds, score_run


class StrategyBenchmarkTests(unittest.TestCase):
    def test_score_run_weights_champion_and_diversity(self):
        score = score_run(
            champion_score=0.8,
            accepted_rate=0.5,
            diversity=0.75,
            budget_utilization=1.0,
        )
        self.assertAlmostEqual(score, 0.77)

    def test_score_run_rejects_invalid_values(self):
        for value in (-0.1, 1.1, float("inf"), float("nan")):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    score_run(
                        champion_score=value,
                        accepted_rate=0.5,
                        diversity=0.5,
                        budget_utilization=0.5,
                    )

    def test_parse_seeds_is_deterministic_and_rejects_duplicates(self):
        self.assertEqual(parse_seeds("11,23,47"), (11, 23, 47))
        with self.assertRaises(Exception):
            parse_seeds("11,11")


if __name__ == "__main__":
    unittest.main()
