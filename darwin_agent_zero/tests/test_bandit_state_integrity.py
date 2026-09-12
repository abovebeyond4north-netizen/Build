import json
import math
import tempfile
import unittest
from pathlib import Path

from dgm_zero.sota_methods import UCBOperatorBandit


class BanditStateIntegrityTests(unittest.TestCase):
    def test_save_and_load_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bandit.json"
            bandit = UCBOperatorBandit(["wrap", "replace"])
            bandit.update("wrap", 0.75)
            bandit.save(path)
            loaded = UCBOperatorBandit.load(path, ["wrap", "replace"])
            self.assertEqual(loaded.arms["wrap"].pulls, 1)
            self.assertAlmostEqual(loaded.arms["wrap"].reward_sum, 0.75)

    def test_negative_pulls_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bandit.json"
            path.write_text(
                json.dumps(
                    {
                        "exploration": 1.4,
                        "arms": {
                            "wrap": {"name": "wrap", "pulls": -1, "reward_sum": 0.0}
                        },
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "pull count"):
                UCBOperatorBandit.load(path, ["wrap"])

    def test_reward_sum_cannot_exceed_number_of_pulls(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bandit.json"
            path.write_text(
                json.dumps(
                    {
                        "exploration": 1.4,
                        "arms": {
                            "wrap": {"name": "wrap", "pulls": 1, "reward_sum": 2.0}
                        },
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "reward sum"):
                UCBOperatorBandit.load(path, ["wrap"])

    def test_invalid_exploration_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bandit.json"
            path.write_text(
                json.dumps({"exploration": 0.0, "arms": {}}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "exploration"):
                UCBOperatorBandit.load(path, ["wrap"])

    def test_non_finite_rewards_fail_closed(self):
        bandit = UCBOperatorBandit(["wrap"])
        for reward in (math.nan, math.inf, -math.inf):
            with self.subTest(reward=reward):
                with self.assertRaisesRegex(ValueError, "finite"):
                    bandit.update("wrap", reward)


if __name__ == "__main__":
    unittest.main()
