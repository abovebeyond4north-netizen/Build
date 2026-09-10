import math
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

    def test_memory_rejects_non_finite_usefulness(self):
        with tempfile.TemporaryDirectory() as tmp:
            bank = KnowledgeBank(Path(tmp))
            with self.assertRaisesRegex(ValueError, "finite"):
                bank.deposit("task", "bad", math.nan)
            with self.assertRaisesRegex(ValueError, "finite"):
                bank.deposit("task", "bad", math.inf)

    def test_memory_rejects_negative_limits(self):
        with tempfile.TemporaryDirectory() as tmp:
            bank = KnowledgeBank(Path(tmp))
            with self.assertRaisesRegex(ValueError, "non-negative"):
                bank.recall(limit=-1)
            with self.assertRaisesRegex(ValueError, "non-negative"):
                bank.prune(-1)

    def test_memory_rejects_empty_kind_and_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            bank = KnowledgeBank(Path(tmp))
            with self.assertRaisesRegex(ValueError, "kind"):
                bank.deposit("", "content")
            with self.assertRaisesRegex(ValueError, "content"):
                bank.deposit("task", "   ")

    def test_memory_prune_keeps_highest_usefulness(self):
        with tempfile.TemporaryDirectory() as tmp:
            bank = KnowledgeBank(Path(tmp))
            bank.deposit("task", "low", 0.1)
            bank.deposit("task", "high", 0.9)
            bank.deposit("task", "mid", 0.5)

            bank.prune(2)
            entries = bank.entries()
            self.assertEqual([entry.content for entry in entries], ["high", "mid"])

    def test_memory_corruption_reports_source_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            bank = KnowledgeBank(Path(tmp))
            bank.deposit("task", "valid", 0.5)
            with bank.path.open("a", encoding="utf-8") as handle:
                handle.write("{broken json\n")

            with self.assertRaisesRegex(ValueError, "line 2"):
                bank.entries()

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
