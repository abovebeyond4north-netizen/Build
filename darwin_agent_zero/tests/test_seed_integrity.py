import unittest

from dgm_zero.evolver import SEED_EXPRESSIONS


class SeedIntegrityTests(unittest.TestCase):
    def test_exact_target_is_not_seeded(self):
        self.assertNotIn("a * a + 3 * b - gcd(a, b)", SEED_EXPRESSIONS)

    def test_mutation_parts_still_allow_discovery(self):
        joined = "\n".join(SEED_EXPRESSIONS)
        self.assertIn("a * a + 3 * b", joined)
        self.assertIn("a * a - gcd(a, b)", joined)


if __name__ == "__main__":
    unittest.main()
