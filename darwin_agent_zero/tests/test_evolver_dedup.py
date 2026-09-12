import tempfile
import unittest
from pathlib import Path

from dgm_zero.archive import Archive
from dgm_zero.evolver import DarwinAgentZero, EvolutionConfig


class EvolverDedupTests(unittest.TestCase):
    def test_run_does_not_re_evaluate_same_expression(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            DarwinAgentZero(
                workspace,
                EvolutionConfig(
                    generations=3,
                    population=6,
                    seed=11,
                    curriculum_enabled=False,
                ),
            ).run()

            records = [
                record
                for record in Archive(workspace).records()
                if record.generation >= 0
            ]
            expressions = [record.expression for record in records]

            self.assertGreaterEqual(len(expressions), 6)
            self.assertEqual(len(expressions), len(set(expressions)))


if __name__ == "__main__":
    unittest.main()
