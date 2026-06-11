import tempfile
import unittest
from pathlib import Path

from dgm_zero.archive import Archive
from dgm_zero.memory import KnowledgeBank
from dgm_zero.oracle import EmpiricalGodelOracle
from dgm_zero.self_instruction import SelfInstructor
from dgm_zero.tools import default_registry


class OracleMemoryTests(unittest.TestCase):
    def test_oracle_accepts_known_solution(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Archive(Path(tmp))
            oracle = EmpiricalGodelOracle(archive)
            decision = oracle.judge("a * a + 3 * b - gcd(a, b)")
            self.assertTrue(decision.accepted)
            self.assertEqual(decision.benchmark.correctness, 1.0)

    def test_memory_recall_orders_usefulness(self):
        with tempfile.TemporaryDirectory() as tmp:
            bank = KnowledgeBank(Path(tmp))
            bank.deposit("task", "low", 0.1)
            bank.deposit("task", "high", 0.9)
            recalled = bank.recall("task", limit=1)
            self.assertEqual(recalled[0].content, "high")

    def test_self_instructor_bootstraps(self):
        with tempfile.TemporaryDirectory() as tmp:
            bank = KnowledgeBank(Path(tmp))
            tasks = SelfInstructor(bank).create_tasks(None)
            self.assertGreaterEqual(len(tasks), 1)

    def test_default_registry_lists_tools(self):
        registry = default_registry()
        self.assertIn("list_tools", registry.names())
        self.assertIn("score_expression", registry.names())


if __name__ == "__main__":
    unittest.main()
