import unittest

from dgm_zero.archive import ArchiveRecord
from dgm_zero.metacognition import MetacognitiveMonitor


def record(index: int, score: float) -> ArchiveRecord:
    return ArchiveRecord(
        id=f"r{index}",
        generation=index,
        parent_id=None,
        expression=f"a + b + {index}",
        score={"weighted_total": score},
        accepted=True,
        reason="test",
        created_at=float(index + 1),
    )


class MetacognitionPlateauTests(unittest.TestCase):
    def test_matching_historical_best_is_detected_as_plateau(self):
        records = [record(index, 0.80) for index in range(25)]
        state = MetacognitiveMonitor().assess(
            records,
            elite_cell_count=12,
            mined_case_count=4,
        )
        self.assertEqual(state.stagnation, 1.0)
        self.assertEqual(state.focus, "escape stagnation")

    def test_meaningful_recent_gain_clears_stagnation(self):
        records = [record(index, 0.70) for index in range(5)]
        records.extend(record(index + 5, 0.80) for index in range(20))
        state = MetacognitiveMonitor().assess(
            records,
            elite_cell_count=12,
            mined_case_count=4,
        )
        self.assertEqual(state.stagnation, 0.0)
        self.assertEqual(state.focus, "raise curriculum")

    def test_small_gain_produces_partial_stagnation(self):
        records = [record(index, 0.80) for index in range(5)]
        records.extend(record(index + 5, 0.82) for index in range(20))
        state = MetacognitiveMonitor().assess(
            records,
            elite_cell_count=12,
            mined_case_count=4,
        )
        self.assertGreater(state.stagnation, 0.5)
        self.assertLess(state.stagnation, 1.0)


if __name__ == "__main__":
    unittest.main()
