import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from dgm_zero.health import RunHealthAuditor


def report(**overrides):
    values = {
        "total_records": 10,
        "accepted_records": 3,
        "champion_expression": "a * a + 3 * b - gcd(a, b)",
        "champion_score": {
            "correctness": 1.0,
            "efficiency": 0.9,
            "novelty": 0.6,
            "safety": 1.0,
            "simplicity": 0.8,
            "generalization": 1.0,
            "weighted_total": 0.9,
        },
        "map_elites_cells": 2,
        "cognitive_state": {
            "confidence": 0.9,
            "uncertainty": 0.1,
            "stagnation": 0.2,
            "diversity": 0.5,
            "safety_pressure": 0.0,
            "focus": "exploration",
            "critique": "healthy search state",
        },
        "operator_bandit": {
            "wrap": {
                "pulls": 1.0,
                "reward_sum": 0.5,
                "mean_reward": 0.5,
            }
        },
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class RunHealthAuditorTests(unittest.TestCase):
    def test_consistent_report_passes(self):
        result = RunHealthAuditor().audit(report())
        self.assertTrue(result.passed)
        self.assertEqual(result.summary, "healthy")

    def test_zero_map_elites_cells_is_not_a_sign_of_healthy_diversity(self):
        result = RunHealthAuditor().audit(report(map_elites_cells=0))
        self.assertFalse(result.passed)
        check = next(item for item in result.checks if item.name == "map_elites_cells")
        self.assertFalse(check.passed)

    def test_accepted_records_cannot_exceed_total_records(self):
        result = RunHealthAuditor().audit(report(total_records=2, accepted_records=3))
        self.assertFalse(result.passed)
        check = next(item for item in result.checks if item.name == "accepted_candidates")
        self.assertFalse(check.passed)

    def test_blank_champion_expression_fails(self):
        result = RunHealthAuditor().audit(report(champion_expression="   "))
        self.assertFalse(result.passed)

    def test_boolean_counts_are_rejected(self):
        result = RunHealthAuditor().audit(report(total_records=True))
        self.assertFalse(result.passed)

    def test_empty_cognitive_or_bandit_state_fails(self):
        self.assertFalse(RunHealthAuditor().audit(report(cognitive_state={})).passed)
        self.assertFalse(RunHealthAuditor().audit(report(operator_bandit={})).passed)

    def test_write_outputs_valid_json_without_temp_residue(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "health_report.json"
            auditor = RunHealthAuditor()
            auditor.write(path, auditor.audit(report()))
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(data["passed"])
            self.assertFalse(path.with_name(".health_report.json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
