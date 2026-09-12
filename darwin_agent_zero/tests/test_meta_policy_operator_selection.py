import tempfile
import unittest
from pathlib import Path

from dgm_zero.evolver import DarwinAgentZero, EvolutionConfig
from dgm_zero.meta_learning import MetaLearningPolicy


class StubBandit:
    def choose(self) -> str:
        return "wrap"


class StubMetaLearner:
    def weighted_modes(self, policy: MetaLearningPolicy) -> list[str]:
        return ["simplify"]


class StubRandom:
    def __init__(self, sample: float) -> None:
        self.sample = sample

    def random(self) -> float:
        return self.sample

    def choice(self, values):
        return values[0]


class MetaPolicyOperatorSelectionTests(unittest.TestCase):
    def make_agent(self) -> DarwinAgentZero:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return DarwinAgentZero(
            Path(tmp.name),
            EvolutionConfig(generations=1, population=1, curriculum_enabled=False),
        )

    def test_policy_weighted_mode_can_drive_exploration(self):
        agent = self.make_agent()
        agent.operator_bandit = StubBandit()
        agent.meta_learner = StubMetaLearner()
        agent.meta_policy = MetaLearningPolicy(exploration_bias=1.0)
        agent.rng = StubRandom(sample=0.0)
        self.assertEqual(agent.choose_operator(generation=1), "simplify")

    def test_ucb_choice_remains_exploitation_path(self):
        agent = self.make_agent()
        agent.operator_bandit = StubBandit()
        agent.meta_learner = StubMetaLearner()
        agent.meta_policy = MetaLearningPolicy(exploration_bias=1.0)
        agent.rng = StubRandom(sample=1.0)
        self.assertEqual(agent.choose_operator(generation=1), "wrap")


if __name__ == "__main__":
    unittest.main()
