import unittest

from dgm_zero.decision_matrix import DecisionMatrix


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


if __name__ == "__main__":
    unittest.main()
