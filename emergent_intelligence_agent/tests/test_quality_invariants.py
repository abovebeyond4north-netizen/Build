import math
import unittest
from types import SimpleNamespace

from emergent_agent.core import AgentConfig, EmergentAgent
from emergent_agent.data_skills import KnowledgeBase
from emergent_agent.evaluation import EvalCase, Evaluator
from emergent_agent.evolution import EvolutionConfig, EvolutionaryOptimizer


class KnowledgeBaseInvariantTests(unittest.TestCase):
    def test_negative_search_and_summary_limits_are_rejected(self):
        kb = KnowledgeBase()
        kb.add("doc", "reasoning decomposition")
        with self.assertRaisesRegex(ValueError, "top_k"):
            kb.search("reasoning", top_k=-1)
        with self.assertRaisesRegex(ValueError, "max_chars"):
            kb.summarize_hits([], max_chars=-1)

    def test_zero_limits_return_empty_output(self):
        kb = KnowledgeBase()
        kb.add("doc", "reasoning decomposition")
        self.assertEqual(kb.search("reasoning", top_k=0), [])
        self.assertEqual(kb.summarize_hits([], max_chars=0), "")

    def test_empty_document_fields_are_rejected(self):
        kb = KnowledgeBase()
        with self.assertRaisesRegex(ValueError, "doc_id"):
            kb.add(" ", "content")
        with self.assertRaisesRegex(ValueError, "text"):
            kb.add("id", " ")

    def test_retrieval_still_ranks_relevant_document_first(self):
        kb = KnowledgeBase()
        kb.add("reasoning", "reasoning uses decomposition checks and evidence")
        kb.add("music", "music uses rhythm harmony and melody")
        hits = kb.search("reasoning decomposition", top_k=2)
        self.assertEqual(hits[0].document.id, "reasoning")
        self.assertGreater(hits[0].score, 0.0)


class EvaluatorInvariantTests(unittest.TestCase):
    def test_weighted_fitness_is_normalized(self):
        class Agent:
            def answer(self, prompt):
                text = "yes" if prompt == "important" else "wrong"
                return SimpleNamespace(answer=text)

        evaluator = Evaluator(
            [
                EvalCase("important", ("yes",), weight=9.0),
                EvalCase("minor", ("no",), weight=1.0),
            ]
        )
        self.assertAlmostEqual(evaluator.fitness(Agent()), 0.9)

    def test_zero_weight_case_does_not_change_fitness(self):
        class Agent:
            def answer(self, prompt):
                return SimpleNamespace(answer="yes")

        evaluator = Evaluator(
            [
                EvalCase("counted", ("yes",), weight=1.0),
                EvalCase("ignored", ("missing",), weight=0.0),
            ]
        )
        self.assertEqual(evaluator.fitness(Agent()), 1.0)

    def test_invalid_eval_weights_are_rejected(self):
        for value in (-1.0, math.nan, math.inf):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "weight"):
                    EvalCase("prompt", ("word",), weight=value)

    def test_duplicate_keywords_do_not_double_count(self):
        case = EvalCase("prompt", ("Safety", "safety", " evaluator "))
        self.assertEqual(case.expected_keywords, ("Safety", "evaluator"))


class EvolutionInvariantTests(unittest.TestCase):
    def test_invalid_evolution_configuration_is_rejected(self):
        invalid = [
            {"population_size": 0},
            {"generations": 0},
            {"plateau_generations": 0},
            {"mutation_rate": -0.1},
            {"mutation_rate": 1.1},
            {"plateau_threshold": -0.1},
            {"plateau_threshold": math.nan},
        ]
        for kwargs in invalid:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    EvolutionConfig(**kwargs)

    def test_non_finite_fitness_fails_closed(self):
        class BadEvaluator:
            def fitness(self, agent):
                return math.nan

        optimizer = EvolutionaryOptimizer(
            EvolutionConfig(population_size=2, generations=1)
        )
        with self.assertRaisesRegex(ValueError, "finite"):
            optimizer.evolve(EmergentAgent(), BadEvaluator())

    def test_single_member_population_is_supported(self):
        class EvaluatorStub:
            def fitness(self, agent):
                return 0.5

        optimizer = EvolutionaryOptimizer(
            EvolutionConfig(population_size=1, generations=2, plateau_generations=1)
        )
        best, records = optimizer.evolve(EmergentAgent(), EvaluatorStub())
        self.assertIsNotNone(best)
        self.assertGreaterEqual(len(records), 1)


class AgentConfigInvariantTests(unittest.TestCase):
    def test_negative_retrieval_configuration_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "max_retrievals"):
            AgentConfig(max_retrievals=-1)

    def test_user_input_must_be_text(self):
        with self.assertRaisesRegex(TypeError, "user_input"):
            EmergentAgent().answer(None)


if __name__ == "__main__":
    unittest.main()
