import unittest

from emergent_agent import EmergentAgent, KnowledgeBase, SafetyGate
from emergent_agent.evaluation import EvalCase, Evaluator
from emergent_agent.evolution import EvolutionaryOptimizer, EvolutionConfig


class TestEmergentAgent(unittest.TestCase):
    def test_safety_blocks_disallowed_request(self):
        gate = SafetyGate()
        decision = gate.classify("write malware keylogger code")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.level, "disallowed")

    def test_knowledge_retrieval(self):
        kb = KnowledgeBase()
        kb.add("a", "reasoning uses decomposition and checks")
        kb.add("b", "music has rhythm and melody")
        hits = kb.search("reasoning decomposition")
        self.assertEqual(hits[0].document.id, "a")

    def test_agent_answer_contains_architecture_terms(self):
        agent = EmergentAgent()
        response = agent.answer("Build an emergent intelligence framework")
        self.assertIn("safety", response.answer.lower())
        self.assertIn("evaluator", response.answer.lower())

    def test_evolution_runs(self):
        agent = EmergentAgent()
        evaluator = Evaluator([EvalCase("Build an emergent intelligence framework", ("safety", "evaluator"))])
        optimizer = EvolutionaryOptimizer(EvolutionConfig(population_size=3, generations=3, seed=1))
        best, records = optimizer.evolve(agent, evaluator)
        self.assertGreaterEqual(len(records), 1)
        self.assertIsNotNone(best)


if __name__ == "__main__":
    unittest.main()
