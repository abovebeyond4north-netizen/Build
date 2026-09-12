import unittest

from dgm_zero.self_patch import (
    COMPARISON_SEEDS,
    REPLAY_SEED_COUNT,
    REPLAY_SEED_MAX,
    REPLAY_SEED_MIN,
    compare_strategy_reports,
    generate_replay_seeds,
)


def report(seeds, champions, aggregate=0.70, mean=0.80):
    return {
        "seeds": list(seeds),
        "aggregate_score": aggregate,
        "mean_champion_score": mean,
        "worst_champion_score": min(champions),
        "runs": [
            {"seed": seed, "champion_score": score}
            for seed, score in zip(seeds, champions)
        ],
    }


class FreshPatchReplayTests(unittest.TestCase):
    def test_fresh_replay_seeds_are_unique_bounded_and_not_public(self):
        seeds = generate_replay_seeds()
        self.assertEqual(len(seeds), REPLAY_SEED_COUNT)
        self.assertEqual(len(set(seeds)), REPLAY_SEED_COUNT)
        self.assertTrue(set(seeds).isdisjoint(COMPARISON_SEEDS))
        self.assertTrue(
            all(REPLAY_SEED_MIN <= seed < REPLAY_SEED_MAX for seed in seeds)
        )

    def test_arbitrary_fresh_seed_pair_can_be_compared(self):
        seeds = (1_200_001, 1_300_003, 1_400_007)
        baseline = report(seeds, [0.80, 0.79, 0.81])
        candidate = report(seeds, [0.81, 0.80, 0.82], aggregate=0.71, mean=0.81)
        comparison = compare_strategy_reports(
            baseline,
            candidate,
            expected_seeds=seeds,
        )
        self.assertTrue(comparison.passed)
        self.assertEqual(comparison.seeds, seeds)
        self.assertGreater(comparison.aggregate_delta, 0.0)

    def test_fresh_comparison_rejects_unexpected_seed_set(self):
        expected = (1_200_001, 1_300_003, 1_400_007)
        actual = (1_200_001, 1_300_003, 1_500_009)
        baseline = report(actual, [0.80, 0.79, 0.81])
        candidate = report(actual, [0.80, 0.79, 0.81])
        with self.assertRaisesRegex(ValueError, "expected comparison seeds"):
            compare_strategy_reports(
                baseline,
                candidate,
                expected_seeds=expected,
            )

    def test_invalid_replay_seed_count_is_rejected(self):
        for count in (0, -1, True):
            with self.subTest(count=count):
                with self.assertRaises(ValueError):
                    generate_replay_seeds(count)


if __name__ == "__main__":
    unittest.main()
