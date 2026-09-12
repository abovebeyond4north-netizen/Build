import math
import unittest
from types import SimpleNamespace

from dgm_zero.health import RunHealthAuditor


def healthy_report():
    return SimpleNamespace(
        total_records=4,
        accepted_records=2,
        champion_expression="a * a + 3 * b - gcd(a, b)",
        champion_score={
            "correctness": 1.0,
            "efficiency": 0.9,
            "novelty": 0.5,
            "safety": 1.0,
            "simplicity": 0.8,
            "generalization": 1.0,
            "weighted_total": 0.9,
        },
        map_elites_cells=2,
        cognitive_state={
            "confidence": 0.9,
            "uncertainty": 0.1,
            "stagnation": 0.2,
            "diversity": 0.5,
            "safety_pressure": 0.0,
            "focus": "raise curriculum",
            "critique": "progressing",
        },
        operator_bandit={
            "append": {
                "pulls": 2.0,
                "reward_sum": 1.0,
                "mean_reward": 0.5,
            }
        },
    )


class HealthStateValidationTests(unittest.TestCase):
    def test_valid_run_state_passes(self):
        report = RunHealthAuditor().audit(healthy_report())
        self.assertTrue(report.passed)

    def test_non_finite_cognitive_state_blocks_checkpoint_health(self):
        candidate = healthy_report()
        candidate.cognitive_state = {
            **candidate.cognitive_state,
            "stagnation": math.nan,
        }
        report = RunHealthAuditor().audit(candidate)
        self.assertFalse(report.passed)
        self.assertFalse(
            next(check for check in report.checks if check.name == "cognitive_state_valid").passed
        )

    def test_impossible_bandit_reward_blocks_checkpoint_health(self):
        candidate = healthy_report()
        candidate.operator_bandit = {
            "append": {
                "pulls": 1.0,
                "reward_sum": 2.0,
                "mean_reward": 2.0,
            }
        }
        report = RunHealthAuditor().audit(candidate)
        self.assertFalse(report.passed)
        self.assertFalse(
            next(check for check in report.checks if check.name == "operator_bandit_valid").passed
        )

    def test_invalid_champion_score_blocks_checkpoint_health(self):
        candidate = healthy_report()
        candidate.champion_score = {"weighted_total": 1.5}
        report = RunHealthAuditor().audit(candidate)
        self.assertFalse(report.passed)
        self.assertFalse(
            next(check for check in report.checks if check.name == "champion_score_valid").passed
        )


if __name__ == "__main__":
    unittest.main()
