import tempfile
import unittest
from pathlib import Path

from dgm_zero.curriculum import CurriculumManager


class CurriculumBiasTests(unittest.TestCase):
    def test_default_bias_preserves_historical_success_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = CurriculumManager(Path(tmp))
            state = manager.update_after_run(0.94)
            self.assertEqual(state.stable_successes, 1)

    def test_high_bias_counts_strong_but_subhistorical_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = CurriculumManager(Path(tmp))
            state = manager.update_after_run(0.935, progression_bias=1.5)
            self.assertEqual(state.stable_successes, 1)

    def test_low_bias_requires_stronger_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = CurriculumManager(Path(tmp))
            state = manager.update_after_run(0.945, progression_bias=0.5)
            self.assertEqual(state.stable_successes, 0)

    def test_two_biased_successes_advance_curriculum(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = CurriculumManager(Path(tmp))
            manager.update_after_run(0.935, progression_bias=1.5)
            state = manager.update_after_run(0.935, progression_bias=1.5)
            self.assertEqual(state.current.level, 1)
            self.assertEqual(state.stable_successes, 0)

    def test_invalid_bias_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = CurriculumManager(Path(tmp))
            with self.assertRaisesRegex(ValueError, "finite and positive"):
                manager.update_after_run(1.0, progression_bias=0.0)


if __name__ == "__main__":
    unittest.main()
