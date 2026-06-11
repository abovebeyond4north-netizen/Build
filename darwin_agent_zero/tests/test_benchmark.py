import unittest

from dgm_zero.benchmark import evaluate_expression


class BenchmarkTests(unittest.TestCase):
    def test_known_expression_solves_cases(self):
        result = evaluate_expression("a * a + 3 * b - gcd(a, b)")
        self.assertEqual(result.correctness, 1.0)

    def test_wrong_expression_scores_lower(self):
        result = evaluate_expression("a + b")
        self.assertLess(result.correctness, 1.0)


if __name__ == "__main__":
    unittest.main()
