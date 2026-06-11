import tempfile
import unittest
from pathlib import Path

from dgm_zero.sota_methods import UCBOperatorBandit, disagreement, pareto_front, regret, uncertainty_score


class FakeRecord:
    def __init__(self, **score):
        self.score = score


class SOTAMethodTests(unittest.TestCase):
    def test_bandit_explores_all_arms(self):
        bandit = UCBOperatorBandit(["a", "b"])
        first = bandit.choose()
        bandit.update(first, 1.0)
        second = bandit.choose()
        self.assertNotEqual(first, second)

    def test_bandit_persists_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bandit.json"
            bandit = UCBOperatorBandit(["wrap", "append"])
            bandit.update("wrap", 0.75)
            bandit.save(path)
            loaded = UCBOperatorBandit.load(path, ["wrap", "append", "replace"])
            self.assertEqual(loaded.arms["wrap"].pulls, 1)
            self.assertAlmostEqual(loaded.arms["wrap"].reward_sum, 0.75)
            self.assertIn("replace", loaded.arms)

    def test_pareto_front_keeps_non_dominated_records(self):
        weak = FakeRecord(correctness=0.2, novelty=0.1, simplicity=0.2, generalization=0.1)
        strong = FakeRecord(correctness=1.0, novelty=0.5, simplicity=0.7, generalization=1.0)
        front = pareto_front([weak, strong])
        self.assertIn(strong, front)
        self.assertNotIn(weak, front)

    def test_uncertainty_and_regret(self):
        self.assertGreater(uncertainty_score({"correctness": 0.0, "generalization": 0.0, "novelty": 0.0}), 0.9)
        self.assertEqual(regret(0.8, 0.5), 0.30000000000000004)

    def test_disagreement(self):
        self.assertGreater(disagreement([1, 2, 2]), 0.0)
        self.assertEqual(disagreement([1, 1, 1]), 0.0)


if __name__ == "__main__":
    unittest.main()
