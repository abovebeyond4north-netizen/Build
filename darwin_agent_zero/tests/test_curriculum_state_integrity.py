import json
import math
import tempfile
import unittest
from pathlib import Path

from dgm_zero.curriculum import CurriculumManager


class CurriculumStateIntegrityTests(unittest.TestCase):
    def test_round_trip_valid_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = CurriculumManager(Path(tmp))
            state = manager.update_after_run(0.95)
            loaded = manager.load()
            self.assertEqual(loaded, state)

    def test_corrupt_json_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = CurriculumManager(Path(tmp))
            manager.path.write_text("{broken", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid curriculum state"):
                manager.load()

    def test_invalid_counts_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = CurriculumManager(Path(tmp))
            payload = {
                "current": {
                    "level": 1,
                    "value_min": -55,
                    "value_max": 55,
                    "train_count": 0,
                    "validation_count": 88,
                    "adversarial_scale": 2,
                },
                "best_score_seen": 0.8,
                "stable_successes": 0,
            }
            manager.path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "case counts"):
                manager.load()

    def test_non_finite_or_out_of_range_champion_score_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = CurriculumManager(Path(tmp))
            for bad in (math.nan, math.inf, -0.1, 1.1, True):
                with self.subTest(bad=bad):
                    with self.assertRaisesRegex(ValueError, "champion_score"):
                        manager.update_after_run(bad)

    def test_atomic_save_leaves_no_temp_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = CurriculumManager(workspace)
            manager.update_after_run(0.95)
            self.assertTrue(manager.path.is_file())
            self.assertEqual(list(workspace.glob(".curriculum.json.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
