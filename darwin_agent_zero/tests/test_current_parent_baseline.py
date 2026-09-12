import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from dgm_zero.evolver import Candidate, DarwinAgentZero, EvolutionConfig


class FakeScore:
    def __init__(self, total: float) -> None:
        self.weighted_total = total

    def as_dict(self) -> dict[str, float]:
        return {
            "correctness": 1.0,
            "efficiency": 1.0,
            "novelty": 0.5,
            "safety": 1.0,
            "simplicity": 1.0,
            "generalization": 1.0,
            "weighted_total": self.weighted_total,
        }


class FakeOracle:
    def __init__(self) -> None:
        self.calls: list[tuple[str, float | None]] = []

    def judge(self, expression: str, parent_total: float | None = None):
        self.calls.append((expression, parent_total))
        total = 0.4 if expression == "a + b" else 0.6
        return SimpleNamespace(
            score=FakeScore(total),
            accepted=True,
            reason="fake current-benchmark result",
        )


class FakeBandit:
    def __init__(self) -> None:
        self.updates: list[tuple[str, float]] = []

    def update(self, name: str, reward: float) -> None:
        self.updates.append((name, reward))


class CurrentParentBaselineTests(unittest.TestCase):
    def test_parent_is_rescored_under_current_oracle(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = DarwinAgentZero(
                Path(tmp),
                EvolutionConfig(generations=1, population=1, curriculum_enabled=False),
            )
            parent = agent.archive.append(
                generation=-1,
                parent_id=None,
                expression="a + b",
                score={"weighted_total": 0.9},
                accepted=True,
                reason="old curriculum score",
            )
            oracle = FakeOracle()
            agent.oracle = oracle

            current = agent.current_parent_total(parent)

            self.assertEqual(current, 0.4)
            self.assertEqual(oracle.calls, [("a + b", None)])

    def test_child_gate_and_operator_reward_use_current_parent_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = DarwinAgentZero(
                Path(tmp),
                EvolutionConfig(generations=1, population=1, curriculum_enabled=False),
            )
            parent = agent.archive.append(
                generation=-1,
                parent_id=None,
                expression="a + b",
                score={"weighted_total": 0.9},
                accepted=True,
                reason="old curriculum score",
            )
            oracle = FakeOracle()
            bandit = FakeBandit()
            agent.oracle = oracle
            agent.operator_bandit = bandit

            agent.evaluate_and_archive(
                Candidate("a * a + b", "wrap"),
                parent,
                0,
                parent_total=0.4,
            )

            self.assertEqual(oracle.calls, [("a * a + b", 0.4)])
            self.assertEqual(len(bandit.updates), 1)
            self.assertEqual(bandit.updates[0][0], "wrap")
            self.assertAlmostEqual(bandit.updates[0][1], 0.2)


if __name__ == "__main__":
    unittest.main()
