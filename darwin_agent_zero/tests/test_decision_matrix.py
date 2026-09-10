import math
import unittest

from dgm_zero.decision_matrix import CandidateScore, DecisionMatrix, DecisionWeights


class DecisionMatrixTests(unittest.TestCase):
    def test_accepts_strong_candidate(self):
        matrix = DecisionMatrix(accept_threshold=0.70)
        score = matrix.score({
            "correctness": 1.0,
            "efficiency": 0.9,
            "novelty": 0.7,
            "safety": 1.0,
            "simplicity": 0.8,
            "generalization": 1.0,
        })
        self.assertTrue(matrix.accepts(score))

    def test_rejects_low_safety_candidate(self):
        matrix = DecisionMatrix(accept_threshold=0.10)
        score = matrix.score({
            "correctness": 1.0,
            "efficiency": 1.0,
            "novelty": 1.0,
            "safety": 0.2,
            "simplicity": 1.0,
            "generalization": 1.0,
        })
        self.assertFalse(matrix.accepts(score))

    def test_negative_decision_weight_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "non-negative"):
            DecisionWeights(correctness=-0.1).normalized()

    def test_non_finite_decision_weight_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "finite"):
            DecisionWeights(correctness=math.nan).normalized()

    def test_non_finite_factor_is_rejected(self):
        matrix = DecisionMatrix()
        with self.assertRaisesRegex(ValueError, "finite"):
            matrix.score({"correctness": math.inf})
        with self.assertRaisesRegex(ValueError, "finite"):
            matrix.score({"correctness": math.nan})

    def test_threshold_must_be_bounded(self):
        with self.assertRaisesRegex(ValueError, "between 0 and 1"):
            DecisionMatrix(accept_threshold=1.1)
        with self.assertRaisesRegex(ValueError, "finite"):
            DecisionMatrix(accept_threshold=math.nan)

    def test_weighted_total_cannot_be_forged_outside_score_range(self):
        score = CandidateScore(
            correctness=1.0,
            efficiency=1.0,
            novelty=1.0,
            safety=1.0,
            simplicity=1.0,
            generalization=1.0,
        )
        with self.assertRaisesRegex(ValueError, "weighted_total"):
            score.with_total(99.0)

    def test_parent_score_must_be_valid(self):
        matrix = DecisionMatrix(accept_threshold=0.5)
        score = matrix.score({
            "correctness": 1.0,
            "efficiency": 1.0,
            "novelty": 1.0,
            "safety": 1.0,
            "simplicity": 1.0,
            "generalization": 1.0,
        })
        with self.assertRaisesRegex(ValueError, "parent_score"):
            matrix.accepts(score, parent_score=math.nan)


if __name__ == "__main__":
    unittest.main()
