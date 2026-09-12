import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from dgm_zero.decision_matrix import CandidateScore
from dgm_zero.evolver import DarwinAgentZero, EvolutionConfig
from dgm_zero.map_elites import MAPElitesGrid


def score(total: float) -> CandidateScore:
    return CandidateScore(
        correctness=1.0,
        efficiency=1.0,
        novelty=1.0,
        safety=1.0,
        simplicity=1.0,
        generalization=1.0,
    ).with_total(total)


class FakeOracle:
    def __init__(self, evidence: dict[str, tuple[float, bool]]) -> None:
        self.evidence = evidence
        self.calls: list[str] = []

    def judge(self, expression: str, parent_total: float | None = None):
        self.calls.append(expression)
        total, accepted = self.evidence[expression]
        return SimpleNamespace(score=score(total), accepted=accepted)


class CurrentArchiveSelectionTests(unittest.TestCase):
    @staticmethod
    def append(agent: DarwinAgentZero, expression: str, total: float, generation: int):
        return agent.archive.append(
            generation=generation,
            parent_id=None,
            expression=expression,
            score=score(total).as_dict(),
            accepted=True,
            reason="historically accepted",
        )

    def test_current_champion_ignores_stale_historical_ranking(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = DarwinAgentZero(Path(tmp), EvolutionConfig(generations=0))
            stale = self.append(agent, "a + b", 0.99, 0)
            current = self.append(
                agent,
                "a * a + 3 * b - gcd(a, b)",
                0.80,
                1,
            )
            agent.map_elites = MAPElitesGrid().build(agent.archive.records())
            agent.oracle = FakeOracle(
                {
                    stale.expression: (0.40, False),
                    current.expression: (0.91, True),
                }
            )

            champion = agent.current_champion()

            self.assertIsNotNone(champion)
            self.assertEqual(champion.record.id, current.id)
            self.assertAlmostEqual(champion.score["weighted_total"], 0.91)

    def test_parent_selection_excludes_currently_invalid_candidate_when_valid_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = DarwinAgentZero(Path(tmp), EvolutionConfig(generations=0, seed=7))
            stale = self.append(agent, "a + b", 0.99, 0)
            valid = self.append(agent, "a * a + 3 * b", 0.70, 1)
            agent.map_elites = MAPElitesGrid().build(agent.archive.records())
            agent.oracle = FakeOracle(
                {
                    stale.expression: (0.55, False),
                    valid.expression: (0.82, True),
                }
            )

            selected = agent.select_parent()

            self.assertIsNotNone(selected)
            self.assertEqual(selected.id, valid.id)

    def test_current_champion_fails_closed_when_archive_no_longer_clears_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = DarwinAgentZero(Path(tmp), EvolutionConfig(generations=0))
            first = self.append(agent, "a + b", 0.95, 0)
            second = self.append(agent, "a * a + b", 0.90, 1)
            agent.map_elites = MAPElitesGrid().build(agent.archive.records())
            agent.oracle = FakeOracle(
                {
                    first.expression: (0.60, False),
                    second.expression: (0.65, False),
                }
            )

            self.assertIsNone(agent.current_champion())
            self.assertIsNotNone(agent.select_parent())

    def test_archive_shortlist_is_bounded_and_preserves_recent_stepping_stones(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = DarwinAgentZero(
                Path(tmp),
                EvolutionConfig(generations=0, elite_parent_limit=4),
            )
            records = [
                self.append(agent, f"a + b + {index}", 0.99 - index * 0.01, index)
                for index in range(8)
            ]
            agent.map_elites = MAPElitesGrid().build(agent.archive.records())

            shortlist = agent.archive_shortlist()

            self.assertLessEqual(len(shortlist), 4)
            self.assertIn(records[-1].id, {record.id for record in shortlist})


if __name__ == "__main__":
    unittest.main()
