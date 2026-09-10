import unittest

from dgm_zero.benchmark import canonical_cases, eval_expr, evaluate_expression


class BenchmarkTests(unittest.TestCase):
    def test_known_expression_solves_cases(self):
        result = evaluate_expression("a * a + 3 * b - gcd(a, b)")
        self.assertEqual(result.correctness, 1.0)

    def test_wrong_expression_scores_lower(self):
        result = evaluate_expression("a + b")
        self.assertLess(result.correctness, 1.0)

    def test_explicit_empty_case_list_stays_empty(self):
        result = evaluate_expression("a + b", [])
        self.assertEqual(result.total, 0)
        self.assertEqual(result.passed, 0)
        self.assertEqual(result.correctness, 0.0)

    def test_division_by_zero_fails_instead_of_becoming_zero(self):
        with self.assertRaises(ZeroDivisionError):
            eval_expr("a // 0", 3, 4)
        with self.assertRaises(ZeroDivisionError):
            eval_expr("a % 0", 3, 4)

    def test_call_keywords_are_rejected_instead_of_ignored(self):
        with self.assertRaisesRegex(ValueError, "keyword arguments"):
            eval_expr("max(a, b, bogus=1)", 3, 4)

    def test_boolean_literals_are_not_treated_as_integer_constants(self):
        with self.assertRaisesRegex(ValueError, "unsupported expression node"):
            eval_expr("True", 3, 4)

    def test_oversized_expression_is_rejected_before_evaluation(self):
        expression = "+".join(["a"] * 300)
        with self.assertRaisesRegex(ValueError, "too complex"):
            eval_expr(expression, 3, 4)

    def test_case_generation_rejects_invalid_bounds(self):
        with self.assertRaisesRegex(ValueError, "non-negative"):
            canonical_cases(count=-1)
        with self.assertRaisesRegex(ValueError, "must not exceed"):
            canonical_cases(value_min=5, value_max=4)


if __name__ == "__main__":
    unittest.main()
