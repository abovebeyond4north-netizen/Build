import ast
import random
import tempfile
import unittest
from pathlib import Path

from dgm_zero.evolver import Candidate, DarwinAgentZero, EvolutionConfig
from dgm_zero.mutation import structural_replace


class StructuralMutationSearchTests(unittest.TestCase):
    def test_structural_replace_is_deterministic_and_changes_expression(self):
        expression = "a * a + 3 * b - gcd(a, b)"
        first = structural_replace(expression, random.Random(17))
        second = structural_replace(expression, random.Random(17))
        self.assertEqual(first, second)
        self.assertNotEqual(first, expression)
        ast.parse(first, mode="eval")

    def test_structural_replace_rejects_invalid_inputs(self):
        with self.assertRaisesRegex(ValueError, "non-empty"):
            structural_replace("", random.Random(1))
        with self.assertRaisesRegex(ValueError, "valid Python"):
            structural_replace("a +", random.Random(1))
        with self.assertRaisesRegex(TypeError, "random.Random"):
            structural_replace("a + b", object())  # type: ignore[arg-type]

    def test_replace_operator_uses_structural_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = DarwinAgentZero(
                Path(tmp),
                EvolutionConfig(
                    generations=1,
                    population=1,
                    seed=23,
                    curriculum_enabled=False,
                    mined_case_limit=0,
                ),
            )
            agent.choose_operator = lambda generation: "replace"  # type: ignore[method-assign]
            candidate = agent.mutate("a * a + 3 * b", 0)
            self.assertEqual(candidate.operator, "replace")
            self.assertNotEqual(candidate.expression, "a * a + 3 * b")
            ast.parse(candidate.expression, mode="eval")

    def test_run_stops_after_generation_with_no_unseen_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = DarwinAgentZero(
                Path(tmp),
                EvolutionConfig(
                    generations=8,
                    population=1,
                    seed=5,
                    curriculum_enabled=False,
                    mined_case_limit=0,
                ),
            )
            agent.self_instruct = (  # type: ignore[method-assign]
                lambda parent, generation: [Candidate("a + b", "seed")]
            )
            report = agent.run()
            self.assertEqual(report.generations, 2)
            self.assertEqual(len(agent.archive.records()), 1)
            search_events = agent.memory.recall("search", limit=4)
            self.assertTrue(search_events)
            self.assertIn("search_space_exhausted", search_events[0].content)


if __name__ == "__main__":
    unittest.main()
