import tempfile
import unittest
from pathlib import Path

from dgm_zero.capability import CapabilityAcquirer
from dgm_zero.objective import ObjectiveCompiler


class ObjectiveEvidenceTests(unittest.TestCase):
    def test_all_builtin_objectives_have_multiple_validation_and_holdout_cases(self):
        compiler = ObjectiveCompiler()
        objectives = (
            "Normalize text",
            "Sequence span",
            "Clamp values",
            "Improve Python debugging ability",
        )
        for objective in objectives:
            with self.subTest(objective=objective):
                spec = compiler.compile(objective)
                self.assertGreaterEqual(len(spec.cases_for("validation")), 3)
                self.assertGreaterEqual(len(spec.cases_for("holdout")), 3)

    def test_strengthened_builtin_suites_remain_acquirable(self):
        compiler = ObjectiveCompiler()
        objectives = (
            "Normalize text",
            "Sequence span",
            "Clamp values",
        )
        for objective in objectives:
            with self.subTest(objective=objective), tempfile.TemporaryDirectory() as tmp:
                report = CapabilityAcquirer(Path(tmp)).acquire(compiler.compile(objective))
                self.assertTrue(report.promoted)
                self.assertEqual(report.validation_score, 1.0)
                self.assertEqual(report.holdout_score, 1.0)
                self.assertEqual(report.holdout_evaluations, 1)


if __name__ == "__main__":
    unittest.main()
