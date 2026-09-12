import tempfile
import unittest
from pathlib import Path

from dgm_zero.evolver import Candidate, DarwinAgentZero, EvolutionConfig


class LineageBalancedEvolverTests(unittest.TestCase):
    def test_population_prefix_spans_distinct_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = DarwinAgentZero(
                Path(tmp),
                EvolutionConfig(
                    generations=1,
                    population=4,
                    seed=29,
                    curriculum_enabled=False,
                    mined_case_limit=0,
                ),
            )
            agent.mutate = (  # type: ignore[method-assign]
                lambda expression, generation: Candidate(
                    f"({expression}) + {generation + 17}",
                    "append",
                )
            )
            candidates = agent.self_instruct(None, 0)
            first_population = candidates[: agent.config.population]
            lineage_keys = [
                candidate.source_expression or candidate.expression
                for candidate in first_population
            ]
            self.assertEqual(len(first_population), 4)
            self.assertEqual(len(set(lineage_keys)), 4)


if __name__ == "__main__":
    unittest.main()
